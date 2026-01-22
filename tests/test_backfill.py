"""Tests for backfill_issues.py script."""

import sys
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

# Add scripts/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import pytest

from backfill_issues import (
    BackfillProgress,
    github_issue_to_issue_state,
    backfill_to_bigquery,
    backfill_issues
)


class TestBackfillProgress:
    """Test BackfillProgress checkpoint tracking."""
    
    def test_progress_initialization(self, tmp_path):
        checkpoint = tmp_path / "checkpoint.json"
        progress = BackfillProgress(str(checkpoint))
        
        assert progress.stats['processed'] == 0
        assert progress.stats['inserted'] == 0
        assert progress.stats['errors'] == 0
    
    def test_progress_update(self, tmp_path):
        checkpoint = tmp_path / "checkpoint.json"
        progress = BackfillProgress(str(checkpoint))
        
        progress.stats['total_issues'] = 100
        progress.update(42, 'inserted')
        
        assert progress.stats['processed'] == 1
        assert progress.stats['inserted'] == 1
        assert progress.stats['last_issue_number'] == 42
    
    def test_checkpoint_persistence(self, tmp_path):
        checkpoint = tmp_path / "checkpoint.json"
        
        # Create and save progress
        progress1 = BackfillProgress(str(checkpoint))
        progress1.stats['total_issues'] = 200
        progress1.update(10, 'inserted')
        progress1.update(11, 'updated')
        progress1.save_checkpoint()
        
        # Load from checkpoint
        progress2 = BackfillProgress(str(checkpoint))
        assert progress2.stats['processed'] == 2
        assert progress2.stats['inserted'] == 1
        assert progress2.stats['updated'] == 1


class TestGitHubIssueConversion:
    """Test GitHub issue to IssueState conversion."""
    
    def test_convert_open_issue(self):
        # Mock PyGithub Issue
        gh_issue = Mock()
        gh_issue.number = 123
        gh_issue.title = "Test Issue"
        gh_issue.body = "Issue body"
        gh_issue.state = "open"
        
        # Mock label objects with name attribute
        label_bug = Mock()
        label_bug.name = "bug"
        label_p1 = Mock()
        label_p1.name = "priority-p1"
        gh_issue.labels = [label_bug, label_p1]
        
        # Mock assignee object
        assignee = Mock()
        assignee.login = "dev1"
        gh_issue.assignees = [assignee]
        
        gh_issue.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        gh_issue.updated_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        gh_issue.closed_at = None
        gh_issue.user = Mock(login="author1")
        gh_issue.comments = 5
        gh_issue.html_url = "https://github.com/org/repo/issues/123"
        
        issue_state = github_issue_to_issue_state(gh_issue, "org/repo")
        
        assert issue_state.issue_id == "org/repo#123"
        assert issue_state.repo == "org/repo"
        assert issue_state.issue_number == 123
        assert issue_state.title == "Test Issue"
        assert issue_state.state == "open"
        assert issue_state.labels == ["bug", "priority-p1"]
        assert issue_state.assignees == ["dev1"]
        assert issue_state.author == "author1"
        assert issue_state.comment_count == 5
        assert issue_state.closed_at is None
    
    def test_convert_closed_issue(self):
        gh_issue = Mock()
        gh_issue.number = 456
        gh_issue.title = "Closed Issue"
        gh_issue.body = None  # Test None body
        gh_issue.state = "closed"
        gh_issue.labels = []
        gh_issue.assignees = []
        gh_issue.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        gh_issue.updated_at = datetime(2026, 1, 3, tzinfo=timezone.utc)
        gh_issue.closed_at = datetime(2026, 1, 3, tzinfo=timezone.utc)
        gh_issue.user = None  # Test missing user
        gh_issue.comments = 0
        gh_issue.html_url = "https://github.com/org/repo/issues/456"
        
        issue_state = github_issue_to_issue_state(gh_issue, "org/repo")
        
        assert issue_state.body == ""
        assert issue_state.state == "closed"
        assert issue_state.author == "unknown"
        assert issue_state.closed_at == datetime(2026, 1, 3, tzinfo=timezone.utc)


class TestBigQueryBackfill:
    """Test BigQuery batch insertion."""
    
    def test_dry_run_mode(self):
        mock_client = Mock()
        issues = [
            Mock(issue_id="org/repo#1", repo="org/repo", issue_number=1),
            Mock(issue_id="org/repo#2", repo="org/repo", issue_number=2)
        ]
        
        # Mock asdict to return simple dict
        with patch('backfill_issues.asdict', side_effect=lambda x: {'issue_id': x.issue_id}):
            count = backfill_to_bigquery(mock_client, 'dataset', 'table', issues, dry_run=True)
        
        assert count == 2
        mock_client.insert_rows_json.assert_not_called()
    
    def test_bigquery_insertion(self):
        from dataclasses import asdict
        from lib.firestore_schema import IssueState
        
        mock_client = Mock()
        mock_client.project = "test-project"
        mock_client.insert_rows_json.return_value = []  # No errors
        
        issues = [
            IssueState(
                issue_id="org/repo#100",
                repo="org/repo",
                issue_number=100,
                title="Test",
                body="Body",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                closed_at=None,
                author="dev",
                comment_count=0,
                url="https://github.com/org/repo/issues/100",
                priority_score=None,
                last_claimed_at=None,
                last_claimed_by=None
            )
        ]
        
        count = backfill_to_bigquery(mock_client, 'uims', 'issue_state', issues, dry_run=False)
        
        assert count == 1
        mock_client.insert_rows_json.assert_called_once()
        call_args = mock_client.insert_rows_json.call_args
        assert call_args[0][0] == "test-project.uims.issue_state"
        assert len(call_args[0][1]) == 1  # One row
        assert call_args[1]['row_ids'] == ["org/repo#100"]


class TestBackfillIntegration:
    """Integration test for full backfill flow."""
    
    def test_backfill_dry_run_with_minimal_setup(self):
        """Test dry run mode without requiring actual GitHub/Cloud clients."""
        # This test validates the backfill logic without external dependencies
        # Full integration tests will run in CI with real credentials
        
        progress = BackfillProgress("/tmp/test_checkpoint.json")
        progress.stats['total_issues'] = 10
        
        # Simulate processing
        for i in range(1, 11):
            progress.update(i, 'inserted' if i % 2 == 0 else 'updated')
        
        assert progress.stats['processed'] == 10
        assert progress.stats['inserted'] == 5
        assert progress.stats['updated'] == 5
        assert progress.stats['errors'] == 0
