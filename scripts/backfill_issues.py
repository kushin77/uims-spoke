#!/usr/bin/env python3
"""Backfill existing GitHub issues into Firestore and BigQuery.

This script migrates historical issues from GCP-landing-zone repository
into the UIMS spoke data layer. It's idempotent and supports chunked processing.

Usage:
    python3 scripts/backfill_issues.py --repo kushin77/GCP-landing-zone --dry-run
    python3 scripts/backfill_issues.py --repo kushin77/GCP-landing-zone --limit 100
    python3 scripts/backfill_issues.py --repo kushin77/GCP-landing-zone --offset 100 --limit 100
"""

from __future__ import annotations  # Enable postponed annotation evaluation

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING

# Add src/ to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lib.firestore_schema import IssueState
from lib.issue_state import IssueStateManager

# Type checking imports (not evaluated at runtime)
if TYPE_CHECKING:
    from github import Github
    from google.cloud import bigquery, firestore

# Optional imports for testing (mocked in unit tests)
DEPENDENCIES_AVAILABLE = True
try:
    from github import Github, Auth
    from google.cloud import bigquery, firestore
    from google.api_core import retry
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    _missing_dependency_error = e
    
    # Only exit if being run as main script (not imported for testing)
    if __name__ == '__main__':
        print(f"ERROR: Missing dependency: {e}", file=sys.stderr)
        print("Install: pip install PyGithub google-cloud-firestore google-cloud-bigquery", file=sys.stderr)
        sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class BackfillProgress:
    """Track backfill progress with checkpoint persistence."""
    
    def __init__(self, checkpoint_file: str = '/tmp/backfill_checkpoint.json'):
        self.checkpoint_file = checkpoint_file
        self.stats = {
            'total_issues': 0,
            'processed': 0,
            'inserted': 0,
            'updated': 0,
            'errors': 0,
            'last_issue_number': None,
            'start_time': datetime.now(timezone.utc).isoformat(),
            'last_checkpoint': None
        }
        self._load_checkpoint()
    
    def _load_checkpoint(self):
        """Load previous progress if available."""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    saved = json.load(f)
                    self.stats.update(saved)
                    logger.info(f"Resumed from checkpoint: {self.stats['processed']} issues processed")
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
    
    def save_checkpoint(self):
        """Save current progress."""
        self.stats['last_checkpoint'] = datetime.now(timezone.utc).isoformat()
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def update(self, issue_number: int, action: str):
        """Update stats (action: 'inserted', 'updated', 'error')."""
        self.stats['processed'] += 1
        self.stats['last_issue_number'] = issue_number
        if action == 'inserted':
            self.stats['inserted'] += 1
        elif action == 'updated':
            self.stats['updated'] += 1
        elif action == 'error':
            self.stats['errors'] += 1
        
        # Save checkpoint every 10 issues
        if self.stats['processed'] % 10 == 0:
            self.save_checkpoint()
            logger.info(f"Progress: {self.stats['processed']}/{self.stats['total_issues']} "
                       f"(inserted={self.stats['inserted']}, updated={self.stats['updated']}, "
                       f"errors={self.stats['errors']})")
    
    def finalize(self):
        """Save final stats and print summary."""
        self.save_checkpoint()
        duration = (datetime.fromisoformat(self.stats['last_checkpoint']) - 
                   datetime.fromisoformat(self.stats['start_time'])).total_seconds()
        
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"Total issues: {self.stats['total_issues']}")
        logger.info(f"Processed: {self.stats['processed']}")
        logger.info(f"Inserted: {self.stats['inserted']}")
        logger.info(f"Updated: {self.stats['updated']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Duration: {duration:.1f}s ({self.stats['processed']/duration:.1f} issues/sec)")
        logger.info("=" * 60)


def github_issue_to_issue_state(gh_issue, repo_name: str) -> IssueState:
    """Convert PyGithub Issue to IssueState."""
    return IssueState(
        issue_id=f"{repo_name}#{gh_issue.number}",
        repo=repo_name,
        issue_number=gh_issue.number,
        title=gh_issue.title,
        body=gh_issue.body or "",
        state=gh_issue.state,  # 'open' or 'closed'
        labels=[label.name for label in gh_issue.labels],
        assignees=[assignee.login for assignee in gh_issue.assignees],
        created_at=gh_issue.created_at.replace(tzinfo=timezone.utc),
        updated_at=gh_issue.updated_at.replace(tzinfo=timezone.utc),
        closed_at=gh_issue.closed_at.replace(tzinfo=timezone.utc) if gh_issue.closed_at else None,
        author=gh_issue.user.login if gh_issue.user else "unknown",
        comment_count=gh_issue.comments,
        url=gh_issue.html_url,
        priority_score=None,  # Will be computed by Smart Selector
        last_claimed_at=None,
        last_claimed_by=None
    )


def backfill_to_bigquery(
    bq_client: bigquery.Client,
    dataset_id: str,
    table_id: str,
    issues: List[IssueState],
    dry_run: bool = False
) -> int:
    """Insert issues into BigQuery. Returns number of rows inserted."""
    if dry_run:
        logger.info(f"[DRY-RUN] Would insert {len(issues)} issues into BigQuery {dataset_id}.{table_id}")
        return len(issues)
    
    table_ref = f"{bq_client.project}.{dataset_id}.{table_id}"
    
    # Convert IssueState to dict for BigQuery
    rows = []
    for issue in issues:
        row = asdict(issue)
        # BigQuery expects datetime strings in ISO format
        for date_field in ['created_at', 'updated_at', 'closed_at', 'last_claimed_at']:
            if row[date_field]:
                row[date_field] = row[date_field].isoformat()
        rows.append(row)
    
    # Insert with streaming (idempotent via insert_id = issue_id)
    errors = bq_client.insert_rows_json(
        table_ref,
        rows,
        row_ids=[issue.issue_id for issue in issues]  # Deduplication
    )
    
    if errors:
        logger.error(f"BigQuery insert errors: {errors}")
        return 0
    
    logger.info(f"Inserted {len(rows)} issues into BigQuery {table_ref}")
    return len(rows)


def backfill_issues(
    repo_name: str,
    github_token: Optional[str] = None,
    firestore_db: Optional[firestore.Client] = None,
    bq_client: Optional[bigquery.Client] = None,
    bq_dataset: str = "uims",
    bq_table: str = "issue_state",
    offset: int = 0,
    limit: Optional[int] = None,
    dry_run: bool = False
) -> BackfillProgress:
    """Backfill issues from GitHub repo to Firestore and BigQuery.
    
    Args:
        repo_name: GitHub repo in format 'owner/repo'
        github_token: GitHub API token (or uses GITHUB_TOKEN env var)
        firestore_db: Firestore client (or creates one)
        bq_client: BigQuery client (or creates one)
        bq_dataset: BigQuery dataset name
        bq_table: BigQuery table name
        offset: Skip first N issues (for chunked processing)
        limit: Process at most N issues (None = all)
        dry_run: If True, only log what would be done
    
    Returns:
        BackfillProgress object with stats
    """
    # Initialize clients
    if not github_token:
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable required")
    
    auth = Auth.Token(github_token)
    gh = Github(auth=auth)
    
    if not firestore_db and not dry_run:
        firestore_db = firestore.Client()
    
    if not bq_client and not dry_run:
        bq_client = bigquery.Client()
    
    # Fetch repository and issues
    logger.info(f"Fetching issues from {repo_name}...")
    repo = gh.get_repo(repo_name)
    
    # Get all issues (both open and closed)
    all_issues = list(repo.get_issues(state='all'))
    
    progress = BackfillProgress()
    progress.stats['total_issues'] = len(all_issues)
    
    logger.info(f"Found {len(all_issues)} total issues in {repo_name}")
    
    # Apply offset and limit
    issues_to_process = all_issues[offset:]
    if limit:
        issues_to_process = issues_to_process[:limit]
    
    logger.info(f"Processing {len(issues_to_process)} issues (offset={offset}, limit={limit})")
    
    # Initialize IssueStateManager (uses emulator-safe fallback if no Firestore)
    issue_manager = IssueStateManager(db=firestore_db)
    
    # Process issues in batches
    batch_size = 50
    for i in range(0, len(issues_to_process), batch_size):
        batch = issues_to_process[i:i+batch_size]
        batch_states = []
        
        for gh_issue in batch:
            try:
                issue_state = github_issue_to_issue_state(gh_issue, repo_name)
                
                # Upsert to Firestore
                if not dry_run:
                    existing = issue_manager.get_issue(issue_state.issue_id)
                    if existing:
                        issue_manager.update_issue(issue_state)
                        progress.update(gh_issue.number, 'updated')
                    else:
                        issue_manager.upsert_issue(issue_state)
                        progress.update(gh_issue.number, 'inserted')
                else:
                    logger.info(f"[DRY-RUN] Would upsert issue #{gh_issue.number}: {gh_issue.title}")
                    progress.update(gh_issue.number, 'inserted')
                
                batch_states.append(issue_state)
                
            except Exception as e:
                logger.error(f"Error processing issue #{gh_issue.number}: {e}")
                progress.update(gh_issue.number, 'error')
        
        # Batch insert to BigQuery
        if batch_states and bq_client:
            try:
                backfill_to_bigquery(bq_client, bq_dataset, bq_table, batch_states, dry_run)
            except Exception as e:
                logger.error(f"BigQuery batch insert failed: {e}")
        
        # Rate limit: GitHub allows 5000 requests/hour
        time.sleep(0.1)
    
    progress.finalize()
    gh.close()
    
    return progress


def main():
    parser = argparse.ArgumentParser(description="Backfill GitHub issues to UIMS spoke")
    parser.add_argument('--repo', required=True, help='GitHub repo (owner/repo)')
    parser.add_argument('--offset', type=int, default=0, help='Skip first N issues')
    parser.add_argument('--limit', type=int, help='Process at most N issues')
    parser.add_argument('--dry-run', action='store_true', help='Log only, no writes')
    parser.add_argument('--bq-dataset', default='uims', help='BigQuery dataset')
    parser.add_argument('--bq-table', default='issue_state', help='BigQuery table')
    
    args = parser.parse_args()
    
    try:
        progress = backfill_issues(
            repo_name=args.repo,
            offset=args.offset,
            limit=args.limit,
            dry_run=args.dry_run,
            bq_dataset=args.bq_dataset,
            bq_table=args.bq_table
        )
        
        # Exit code based on errors
        sys.exit(0 if progress.stats['errors'] == 0 else 1)
        
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
