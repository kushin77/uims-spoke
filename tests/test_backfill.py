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
        gh_issue.labels = [Mock(name="bug"), Mock(name="priority-p1")]
        gh_issue.assignees = [Mock(login="dev1")]
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
    
    @patch('backfill_issues.Github')
    @patch('backfill_issues.firestore.Client')
    @patch('backfill_issues.bigquery.Client')
    def test_backfill_dry_run(self, mock_bq, mock_fs, mock_gh):
        # Mock GitHub repo and issues
        mock_repo = Mock()
        mock_issue1 = Mock()
        mock_issue1.number = 1
        mock_issue1.title = "Issue 1"
        mock_issue1.body = "Body 1"
        mock_issue1.state = "open"
        mock_issue1.labels = []
        mock_issue1.assignees = []
        mock_issue1.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_issue1.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_issue1.closed_at = None
        mock_issue1.user = Mock(login="dev1")
        mock_issue1.comments = 0
        mock_issue1.html_url = "https://github.com/org/repo/issues/1"
        
        mock_repo.get_issues.return_value = [mock_issue1]
        mock_gh.return_value.get_repo.return_value = mock_repo
        
        progress = backfill_issues(
            repo_name="org/repo",
            github_token="fake-token",
            dry_run=True,
            limit=10
        )
        
        assert progress.stats['total_issues'] == 1
        assert progress.stats['processed'] == 1
        mock_fs.assert_not_called()  # Dry run shouldn't create Firestore client
        mock_bq.assert_not_called()
    
    @patch('backfill_issues.Github')
    def test_backfill_with_offset_limit(self, mock_gh):
        mock_repo = Mock()
        mock_issues = [Mock(number=i, title=f"Issue {i}") for i in range(1, 101)]
        for issue in mock_issues:
            issue.body = "Body"
            issue.state = "open"
            issue.labels = []
            issue.assignees = []
            issue.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            issue.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            issue.closed_at = None
            issue.user = Mock(login="dev")
            issue.comments = 0
            issue.html_url = f"https://github.com/org/repo/issues/{issue.number}"
        
        mock_repo.get_issues.return_value = mock_issues
        mock_gh.return_value.get_repo.return_value = mock_repo
        
        # Process issues 51-60 (offset=50, limit=10)
        progress = backfill_issues(
            repo_name="org/repo",
            github_token="fake-token",
            offset=50,
            limit=10,
            dry_run=True
        )
        
        assert progress.stats['total_issues'] == 100
        assert progress.stats['processed'] == 10
        # Last processed should be issue #60
        assert progress.stats['last_issue_number'] == 60
