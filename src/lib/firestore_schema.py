from dataclasses import dataclass
from typing import Optional, Callable, Dict, Tuple, List
from datetime import datetime
import time
import threading


@dataclass
class IssueState:
    """Unified issue state for GitHub issues with smart selector metadata.
    
    Combines GitHub issue data with UIMS spoke-specific fields for priority scoring,
    assignment tracking, and workflow state.
    """
    # Core identifiers
    issue_id: str  # Format: "owner/repo#number"
    repo: str  # Format: "owner/repo"
    issue_number: int
    
    # GitHub issue content
    title: str
    body: str
    state: str  # 'open' or 'closed'
    labels: List[str]
    assignees: List[str]
    author: str
    url: str
    
    # Timestamps (timezone-aware datetime objects)
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    
    # Engagement metrics
    comment_count: int = 0
    
    # UIMS spoke-specific fields
    priority_score: Optional[float] = None  # Computed by Smart Selector
    last_claimed_at: Optional[datetime] = None
    last_claimed_by: Optional[str] = None
    
    # Legacy fields (for backward compatibility)
    current_status: Optional[str] = None  # Deprecated: use 'state'
    score: float = 0.0  # Deprecated: use 'priority_score'
    version: int = 0  # For optimistic locking
    assignee: Optional[str] = None  # Deprecated: use 'last_claimed_by'
    project: Optional[str] = None  # Deprecated: use 'repo'


class LockError(Exception):
    pass


class InMemoryLockManager:
    """Simple in-memory lock manager used for local tests and as a fallback.

    Supports TTL-based locks and allows injecting a custom time function
    for deterministic unit tests.
    """

    def __init__(self, time_fn: Optional[Callable[[], float]] = None):
        self._time = time_fn or time.time
        self._locks: Dict[str, Tuple[str, float]] = {}
        self._mutex = threading.Lock()

    def acquire_lock(self, lock_id: str, owner: str, ttl_seconds: int) -> bool:
        """Attempt to acquire a lock.

        Returns True if acquired, False if lock held by someone else and not expired.
        """
        now = self._time()
        expiry = now + int(ttl_seconds)
        with self._mutex:
            entry = self._locks.get(lock_id)
            if entry is None:
                self._locks[lock_id] = (owner, expiry)
                return True

            existing_owner, existing_expiry = entry
            if existing_expiry <= now:
                # expired -> steal it
                self._locks[lock_id] = (owner, expiry)
                return True

            # held and not expired
            return False

    def release_lock(self, lock_id: str, owner: str) -> bool:
        """Release a lock if owned by `owner`. Returns True if released."""
        now = self._time()
        with self._mutex:
            entry = self._locks.get(lock_id)
            if entry is None:
                return False
            existing_owner, existing_expiry = entry
            if existing_owner != owner and existing_expiry > now:
                # someone else owns it and it's not expired
                return False
            # remove lock
            try:
                del self._locks[lock_id]
            except KeyError:
                pass
            return True

    def is_locked(self, lock_id: str) -> bool:
        now = self._time()
        with self._mutex:
            entry = self._locks.get(lock_id)
            if entry is None:
                return False
            _, expiry = entry
            return expiry > now

    def get_owner(self, lock_id: str) -> Optional[str]:
        now = self._time()
        with self._mutex:
            entry = self._locks.get(lock_id)
            if entry is None:
                return None
            owner, expiry = entry
            if expiry <= now:
                return None
            return owner


__all__ = ["IssueState", "InMemoryLockManager"]
