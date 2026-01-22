"""
Cluster engine for semantic similarity detection and duplicate grouping.

Uses FAISS for efficient nearest-neighbor search.
"""

from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import numpy as np

from src.semantic_clustering.embeddings import EmbeddingsModel, normalize_embedding, cosine_similarity


@dataclass
class DuplicateCluster:
    """Represents a cluster of similar/duplicate issues."""
    
    cluster_id: str
    members: List[int]  # Issue numbers in cluster
    similarity_score: float  # Average similarity within cluster
    primary_issue: int  # First/oldest issue in cluster
    
    def __post_init__(self):
        """Validate cluster data."""
        if not self.members:
            raise ValueError("Cluster must have at least one member")
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError("Similarity score must be in [0, 1]")


@dataclass
class SimilarityResult:
    """Result of similarity query."""
    
    issue_number: int
    similarity: float
    distance: float  # For FAISS: L2 distance


class ClusterEngine:
    """Engine for finding duplicate and similar issues using semantic embeddings.
    
    Workflow:
    1. add_issue() - Add issues to engine
    2. build_index() - Create FAISS index for efficient search
    3. find_duplicates() - Find clusters of similar issues
    4. query_similar() - Find similar issues to a query text
    """

    def __init__(self, model: EmbeddingsModel, similarity_threshold: float = 0.85):
        """Initialize cluster engine.
        
        Args:
            model: EmbeddingsModel instance for generating embeddings
            similarity_threshold: Cosine similarity threshold for considering
                                  issues as duplicates (0-1)
        """
        self.model = model
        self.similarity_threshold = similarity_threshold
        
        self.issues: Dict[int, Dict] = {}  # issue_number -> issue data
        self.embeddings: Dict[int, np.ndarray] = {}  # issue_number -> embedding
        self.issue_ids: List[int] = []  # Ordered list for FAISS index
        self.embeddings_matrix: Optional[np.ndarray] = None  # N x dim matrix
        
        # FAISS index (lazy initialized)
        self.index: Optional['faiss.Index'] = None

    def add_issue(self, issue: Dict) -> None:
        """Add an issue to the engine.
        
        Issue dict should have: number, title, body, created_at
        
        Args:
            issue: Issue data dictionary
        """
        issue_num = issue['number']
        
        # Generate embedding from title + body
        text = f"{issue.get('title', '')} {issue.get('body', '')}"
        embedding = normalize_embedding(self.model.embed(text))
        
        self.issues[issue_num] = issue
        self.embeddings[issue_num] = embedding

    def build_index(self) -> None:
        """Build FAISS index for efficient similarity search.
        
        Must be called after adding issues, before using query_similar().
        """
        if not self.embeddings:
            raise ValueError("No issues added to engine")
        
        # Import FAISS (allow mocking for tests)
        try:
            import faiss
        except ImportError:
            raise ImportError(
                "faiss not installed. "
                "Install with: pip install faiss-cpu or faiss-gpu"
            )
        
        # Create matrix of embeddings
        self.issue_ids = sorted(self.embeddings.keys())
        embeddings_list = [self.embeddings[issue_num] for issue_num in self.issue_ids]
        self.embeddings_matrix = np.vstack(embeddings_list).astype(np.float32)
        
        # Create FAISS index (using L2 distance on normalized vectors)
        dimension = self.embeddings_matrix.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(self.embeddings_matrix)

    def find_duplicates(self) -> List[DuplicateCluster]:
        """Find clusters of duplicate/similar issues.
        
        Uses greedy clustering:
        1. Start with each issue as singleton cluster
        2. Find pairs with similarity > threshold
        3. Merge into transitive closure groups
        
        Returns:
            List of DuplicateCluster objects
        """
        if not self.embeddings:
            return []
        
        # Build index if not already done
        if self.index is None:
            self.build_index()
        
        # Find all pairs with similarity > threshold
        pairs = self._find_similar_pairs()
        
        # Use union-find to group issues into clusters (transitive closure)
        uf = UnionFind(list(self.issues.keys()))
        for issue1, issue2, sim in pairs:
            uf.union(issue1, issue2)
        
        # Group issues by cluster
        clusters_dict: Dict[int, List[tuple]] = {}  # root -> [(issue, similarity)]
        for issue1, issue2, sim in pairs:
            root = uf.find(issue1)
            if root not in clusters_dict:
                clusters_dict[root] = []
            clusters_dict[root].append((issue1, issue2, sim))
        
        # Create DuplicateCluster objects
        clusters = []
        for idx, (root, pairs_in_cluster) in enumerate(clusters_dict.items()):
            members = list(uf.get_group(root))
            
            # Calculate average similarity in cluster
            if pairs_in_cluster:
                avg_sim = np.mean([sim for _, _, sim in pairs_in_cluster])
            else:
                avg_sim = 1.0
            
            # Primary issue is the oldest/first one
            primary = min(members, key=lambda n: (
                self.issues[n].get('created_at', datetime.now()),
                n
            ))
            
            cluster = DuplicateCluster(
                cluster_id=f"cluster_{root}",
                members=sorted(members),
                similarity_score=float(avg_sim),
                primary_issue=primary,
            )
            clusters.append(cluster)
        
        return sorted(clusters, key=lambda c: len(c.members), reverse=True)

    def _find_similar_pairs(self) -> List[tuple]:
        """Find all pairs of issues with similarity > threshold.
        
        Returns:
            List of (issue1, issue2, similarity) tuples
        """
        pairs = []
        issue_nums = sorted(self.issues.keys())
        
        for i, issue1 in enumerate(issue_nums):
            for issue2 in issue_nums[i+1:]:
                emb1 = self.embeddings[issue1]
                emb2 = self.embeddings[issue2]
                
                sim = cosine_similarity(emb1, emb2)
                
                if sim >= self.similarity_threshold:
                    pairs.append((issue1, issue2, sim))
        
        return pairs

    def query_similar(self, query_text: str, top_k: int = 5) -> List[SimilarityResult]:
        """Find issues similar to a query text.
        
        Args:
            query_text: Text to search for similar issues
            top_k: Number of results to return
            
        Returns:
            List of SimilarityResult objects, sorted by similarity (descending)
        """
        if self.index is None:
            raise ValueError("Index not built. Call build_index() first.")
        
        # Embed the query
        query_embedding = normalize_embedding(self.model.embed(query_text))
        query_matrix = query_embedding.reshape(1, -1).astype(np.float32)
        
        # Search in FAISS
        distances, indices = self.index.search(query_matrix, min(top_k, len(self.issue_ids)))
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for invalid results
                continue
            
            issue_num = self.issue_ids[idx]
            # Convert L2 distance back to similarity (for normalized vectors)
            # L2 distance = sqrt(2 - 2*similarity) for normalized vectors
            # similarity = (2 - L2_dist^2) / 2
            similarity = 1.0 - (dist / 2.0)
            similarity = max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
            
            result = SimilarityResult(
                issue_number=issue_num,
                similarity=similarity,
                distance=float(dist),
            )
            results.append(result)
        
        return results

    def clear(self) -> None:
        """Clear all data from engine."""
        self.issues.clear()
        self.embeddings.clear()
        self.issue_ids.clear()
        self.embeddings_matrix = None
        self.index = None

    def __len__(self) -> int:
        """Return number of issues in engine."""
        return len(self.issues)


class UnionFind:
    """Union-Find (Disjoint Set) data structure for cluster grouping."""
    
    def __init__(self, elements: List[int]):
        """Initialize with a list of elements."""
        self.parent = {elem: elem for elem in elements}
        self.rank = {elem: 0 for elem in elements}
    
    def find(self, x: int) -> int:
        """Find root of set containing x (with path compression)."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x: int, y: int) -> None:
        """Union sets containing x and y."""
        root_x = self.find(x)
        root_y = self.find(y)
        
        if root_x == root_y:
            return
        
        # Union by rank
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1
    
    def get_group(self, element: int) -> Set[int]:
        """Get all elements in the same group as element."""
        root = self.find(element)
        return {x for x in self.parent if self.find(x) == root}


__all__ = [
    'ClusterEngine',
    'DuplicateCluster',
    'SimilarityResult',
]
