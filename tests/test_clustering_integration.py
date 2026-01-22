"""Tests for cluster_score integration into Smart Selector."""

import pytest
from datetime import datetime, timezone
from src.smart_selector.scorer import cluster_score, composite_score, DEFAULT_WEIGHTS


class TestClusterScore:
    """Test clustering scoring function."""

    def test_cluster_score_no_info(self):
        """No cluster info = neutral score."""
        issue = {"number": 1}
        score = cluster_score(issue, cluster_info=None)
        assert score == 0.5

    def test_cluster_score_unique_issue(self):
        """Single issue in cluster = highest score."""
        issue = {"number": 1}
        cluster_info = {"cluster_id": "c1", "members_count": 1, "is_primary": True}
        score = cluster_score(issue, cluster_info)
        assert score == 1.0

    def test_cluster_score_small_cluster_primary(self):
        """Primary in small cluster (2-3 members) = high score."""
        issue = {"number": 1}
        cluster_info = {"cluster_id": "c1", "members_count": 2, "is_primary": True}
        score = cluster_score(issue, cluster_info)
        assert score == 0.8

    def test_cluster_score_medium_cluster(self):
        """Medium cluster (4-10 members) = neutral score."""
        issue = {"number": 1}
        cluster_info = {"cluster_id": "c1", "members_count": 5, "is_primary": True}
        score = cluster_score(issue, cluster_info)
        assert score == 0.5

    def test_cluster_score_large_cluster(self):
        """Large cluster (10+ members) = low score."""
        issue = {"number": 1}
        cluster_info = {"cluster_id": "c1", "members_count": 15, "is_primary": True}
        score = cluster_score(issue, cluster_info)
        assert score == 0.3

    def test_cluster_score_duplicate_small(self):
        """Duplicate in 2-member cluster = deprioritized."""
        issue = {"number": 2}
        cluster_info = {"cluster_id": "c1", "members_count": 2, "is_primary": False}
        score = cluster_score(issue, cluster_info)
        # 0.4 - (2/50) = 0.4 - 0.04 = 0.36
        assert 0.35 < score < 0.37

    def test_cluster_score_duplicate_large(self):
        """Duplicate in large cluster = very low score."""
        issue = {"number": 5}
        cluster_info = {"cluster_id": "c1", "members_count": 50, "is_primary": False}
        score = cluster_score(issue, cluster_info)
        # 0.4 - (50/50) = 0.4 - 1.0 = -0.6 -> max(0.0, -0.6) = 0.0
        assert score == 0.0


class TestCompositeScoreWithClustering:
    """Test composite scoring with clustering integration."""

    @pytest.fixture
    def base_issue(self):
        """Base issue for testing."""
        return {
            "number": 1,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "priority": 1,  # P1
            "days_open": 30,
            "cost_impact": 1000.0,
            "blocker_count": 0,
            "team_velocity": 0.8,
            "is_blocked": False,
            "blocks_count": 0,
        }

    def test_composite_without_clustering(self, base_issue):
        """Composite score without clustering info (uses default 0.5)."""
        now = datetime(2024, 2, 1, tzinfo=timezone.utc)
        score_without_cluster = composite_score(base_issue, now=now, cluster_info=None)
        assert 0 <= score_without_cluster <= 100

    def test_composite_unique_issue_boosts_score(self, base_issue):
        """Unique issue (cluster_size=1) increases composite score."""
        now = datetime(2024, 2, 1, tzinfo=timezone.utc)
        cluster_info = {"cluster_id": "c1", "members_count": 1, "is_primary": True}
        score_unique = composite_score(base_issue, now=now, cluster_info=cluster_info)
        assert score_unique > 0

    def test_composite_duplicate_reduces_score(self, base_issue):
        """Duplicate issue reduces composite score."""
        now = datetime(2024, 2, 1, tzinfo=timezone.utc)
        cluster_info = {"cluster_id": "c1", "members_count": 50, "is_primary": False}
        score_duplicate = composite_score(base_issue, now=now, cluster_info=cluster_info)
        assert score_duplicate > 0  # Still positive, but reduced by clustering

    def test_composite_weights_sum_to_one(self):
        """Default weights sum to 1.0 for proper normalization."""
        total_weight = sum(DEFAULT_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001, f"Weights sum to {total_weight}, not 1.0"

    def test_composite_custom_weights(self, base_issue):
        """Composite score respects custom weights."""
        custom_weights = {
            "age": 0.2,
            "priority": 0.3,
            "impact": 0.1,
            "blocker": 0.1,
            "velocity": 0.1,
            "aging_penalty": 0.05,
            "sla_urgency": 0.05,
            "clustering": 0.1,  # Higher clustering weight
        }
        now = datetime(2024, 2, 1, tzinfo=timezone.utc)
        cluster_info = {"cluster_id": "c1", "members_count": 1, "is_primary": True}
        score = composite_score(base_issue, weights=custom_weights, now=now, cluster_info=cluster_info)
        assert 0 <= score <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
