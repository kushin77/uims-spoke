"""
Semantic Clustering Module

Provides semantic similarity detection and duplicate grouping for issues.

Key Components:
- EmbeddingsModel: Generate semantic embeddings using Sentence-BERT or Cohere
- ClusterEngine: Find duplicate and similar issues using FAISS index
- DuplicateCluster: Result structure for issue clusters
"""

from src.semantic_clustering.embeddings import (
    EmbeddingsModel,
    normalize_embedding,
    cosine_similarity,
)
from src.semantic_clustering.cluster_engine import (
    ClusterEngine,
    DuplicateCluster,
    SimilarityResult,
)

__all__ = [
    'EmbeddingsModel',
    'normalize_embedding',
    'cosine_similarity',
    'ClusterEngine',
    'DuplicateCluster',
    'SimilarityResult',
]
