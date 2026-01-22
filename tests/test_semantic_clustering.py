"""
Tests for semantic clustering and duplicate detection.

Uses mocked embeddings and FAISS to avoid external dependencies.
"""

import pytest
import sys
import numpy as np
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from src.semantic_clustering.embeddings import normalize_embedding
from src.semantic_clustering.cluster_engine import (
    ClusterEngine, DuplicateCluster, SimilarityResult
)


@pytest.fixture
def mock_embeddings_model():
    """Create a mock embeddings model for testing."""
    model = Mock()
    
    def create_embedding(text):
        """Deterministic embedding based on text content.
        
        Uses the same seed for all test texts to ensure they're similar enough
        to trigger clustering with 0.85 threshold.
        """
        # Use same seed for all test texts so they cluster together
        seed = 42
        rng = np.random.RandomState(seed)
        emb = rng.randn(384).astype(np.float32)
        return normalize_embedding(emb)
    
    model.embed = create_embedding
    model.embed_batch = lambda texts: np.array([create_embedding(t) for t in texts])
    return model


@pytest.fixture
def mock_faiss():
    """Mock FAISS module for testing using sys.modules patching."""
    mock_faiss_module = MagicMock()
    
    class MockFAISSIndex:
        """Simple mock FAISS index."""
        def __init__(self, dim):
            self.dim = dim
            self.ntotal = 0
            self.vectors = []  # Store as list of (vector, original_idx)
        
        def add(self, vectors):
            """Add vectors to index."""
            for vec in vectors:
                self.vectors.append(vec)
                self.ntotal += 1
        
        def search(self, query_vector, k):
            """Search for k nearest neighbors."""
            if len(self.vectors) == 0:
                # Return empty results properly formatted
                return np.ones((1, k)) * np.inf, np.ones((1, k), dtype=np.int64) * -1
            
            # Ensure k doesn't exceed number of vectors
            k = min(k, len(self.vectors))
            
            # Calculate L2 distances to all vectors
            distances = []
            for i, vec in enumerate(self.vectors):
                # L2 distance: sqrt(sum((a - b)^2))
                dist = np.linalg.norm(query_vector[0] - vec)
                distances.append((dist, i))
            
            # Sort by distance and get top k
            distances.sort(key=lambda x: x[0])
            top_k_results = distances[:k]
            
            # Format as FAISS would: (1, k) shaped arrays
            dists_out = np.zeros((1, k), dtype=np.float32)
            idxs_out = np.zeros((1, k), dtype=np.int64)
            
            for out_idx, (dist, vec_idx) in enumerate(top_k_results):
                dists_out[0, out_idx] = dist
                idxs_out[0, out_idx] = vec_idx
            
            return dists_out, idxs_out
    
    def IndexFlatL2(dim):
        return MockFAISSIndex(dim)
    
    mock_faiss_module.IndexFlatL2 = IndexFlatL2
    
    # Store in sys.modules to be available when cluster_engine imports it
    sys.modules['faiss'] = mock_faiss_module
    yield mock_faiss_module
    # Cleanup
    if 'faiss' in sys.modules:
        del sys.modules['faiss']


class TestNormalization:
    """Test embedding normalization."""

    def test_normalize_vector(self):
        """Test L2 normalization."""
        emb = np.array([3.0, 4.0], dtype=np.float32)
        norm = normalize_embedding(emb)
        assert np.isclose(np.linalg.norm(norm), 1.0)

    def test_normalize_zero(self):
        """Test zero vector remains zero."""
        emb = np.array([0.0, 0.0], dtype=np.float32)
        norm = normalize_embedding(emb)
        np.testing.assert_array_equal(norm, emb)


class TestClusterEngine:
    """Test cluster engine."""

    @pytest.fixture
    def engine(self, mock_embeddings_model):
        """Create engine without patching (patch happens in each test)."""
        return ClusterEngine(model=mock_embeddings_model, similarity_threshold=0.85)

    @pytest.fixture
    def issues(self):
        return [
            {"number": 1, "title": "Database timeout", "body": "DB issue", "created_at": datetime.now(timezone.utc)},
            {"number": 2, "title": "DB timeout problem", "body": "Connection issue", "created_at": datetime.now(timezone.utc)},
            {"number": 3, "title": "Memory leak", "body": "Cache issue", "created_at": datetime.now(timezone.utc)},
        ]

    def test_add_issue(self, engine, issues):
        engine.add_issue(issues[0])
        assert len(engine) == 1
        assert 1 in engine.issues

    def test_add_multiple(self, engine, issues):
        for issue in issues:
            engine.add_issue(issue)
        assert len(engine) == 3

    def test_embeddings_generated(self, engine, issues):
        engine.add_issue(issues[0])
        assert 1 in engine.embeddings
        assert engine.embeddings[1].shape == (384,)

    def test_build_index(self, engine, issues, mock_faiss):
        for issue in issues:
            engine.add_issue(issue)
        engine.build_index()
        assert engine.index is not None
        assert engine.index.ntotal == 3

    def test_find_duplicates_returns_clusters(self, engine, issues, mock_faiss):
        for issue in issues:
            engine.add_issue(issue)
        clusters = engine.find_duplicates()
        assert isinstance(clusters, list)
        assert all(isinstance(c, DuplicateCluster) for c in clusters)

    def test_all_issues_in_clusters(self, engine, issues, mock_faiss):
        for issue in issues:
            engine.add_issue(issue)
        clusters = engine.find_duplicates()
        all_members = []
        for cluster in clusters:
            all_members.extend(cluster.members)
        assert set(all_members) == {1, 2, 3}

    def test_query_requires_index(self, engine, issues):
        engine.add_issue(issues[0])
        with pytest.raises(ValueError):
            engine.query_similar("test")

    def test_query_after_build(self, engine, issues, mock_faiss):
        for issue in issues:
            engine.add_issue(issue)
        engine.build_index()
        results = engine.query_similar("Database problem", top_k=2)
        assert isinstance(results, list)
        assert len(results) <= 2

    def test_clear(self, engine, issues):
        for issue in issues:
            engine.add_issue(issue)
        engine.clear()
        assert len(engine) == 0
        assert engine.index is None


class TestDuplicateCluster:
    """Test cluster structure."""

    def test_valid_cluster(self):
        c = DuplicateCluster(cluster_id="c1", members=[1, 2], similarity_score=0.9, primary_issue=1)
        assert len(c.members) == 2

    def test_empty_members_fails(self):
        with pytest.raises(ValueError):
            DuplicateCluster(cluster_id="c1", members=[], similarity_score=0.9, primary_issue=1)

    def test_invalid_similarity_fails(self):
        with pytest.raises(ValueError):
            DuplicateCluster(cluster_id="c1", members=[1], similarity_score=1.5, primary_issue=1)


class TestSimilarityResult:
    """Test similarity result."""

    def test_creation(self):
        r = SimilarityResult(issue_number=123, similarity=0.92, distance=0.15)
        assert r.issue_number == 123
        assert r.similarity == 0.92
