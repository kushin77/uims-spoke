"""Tests for updated firestore_schema with full GitHub issue fields."""

from src.lib.firestore_schema import InMemoryLockManager, IssueState
from datetime import datetime, timezone


def test_issue_state_with_github_fields():
    """Test IssueState dataclass with full GitHub issue data."""
    now = datetime(2026, 1, 22, tzinfo=timezone.utc)
    s = IssueState(
        issue_id="org/repo#1",
        repo="org/repo",
        issue_number=1,
        title="Test Issue",
        body="Issue body",
        state="open",
        labels=["bug", "priority-p1"],
        assignees=["alice"],
        author="bob",
        url="https://github.com/org/repo/issues/1",
        created_at=now,
        updated_at=now,
        comment_count=5,
        priority_score=0.75,
        version=1,
    )
    
    # GitHub fields
    assert s.issue_id == "org/repo#1"
    assert s.repo == "org/repo"
    assert s.issue_number == 1
    assert s.title == "Test Issue"
    assert s.body == "Issue body"
    assert s.state == "open"
    assert s.labels == ["bug", "priority-p1"]
    assert s.assignees == ["alice"]
    assert s.author == "bob"
    assert s.url == "https://github.com/org/repo/issues/1"
    assert s.created_at == now
    assert s.updated_at == now
    assert s.closed_at is None
    assert s.comment_count == 5
    
    # UIMS fields
    assert s.priority_score == 0.75
    assert s.version == 1
    assert s.last_claimed_at is None
    assert s.last_claimed_by is None


def test_issue_state_with_minimal_fields():
    """Test IssueState with only required fields."""
    now = datetime(2026, 1, 22, tzinfo=timezone.utc)
    s = IssueState(
        issue_id="org/repo#2",
        repo="org/repo",
        issue_number=2,
        title="Minimal Issue",
        body="",
        state="open",
        labels=[],
        assignees=[],
        author="alice",
        url="https://github.com/org/repo/issues/2",
        created_at=now,
        updated_at=now,
    )
    
    assert s.issue_id == "org/repo#2"
    assert s.title == "Minimal Issue"
    assert s.body == ""
    assert s.labels == []
    assert s.assignees == []
    assert s.comment_count == 0  # Default
    assert s.priority_score is None  # Default


def test_issue_state_closed():
    """Test IssueState for closed issue."""
    created = datetime(2026, 1, 20, tzinfo=timezone.utc)
    closed = datetime(2026, 1, 22, 12, 0, tzinfo=timezone.utc)
    
    s = IssueState(
        issue_id="org/repo#3",
        repo="org/repo",
        issue_number=3,
        title="Closed Issue",
        body="Fixed",
        state="closed",
        labels=["bug"],
        assignees=[],
        author="bob",
        url="https://github.com/org/repo/issues/3",
        created_at=created,
        updated_at=closed,
        closed_at=closed,
        comment_count=10,
    )
    
    assert s.state == "closed"
    assert s.closed_at == closed
    assert s.comment_count == 10


def test_inmemory_lock_manager_acquire_and_release():
    """Test InMemoryLockManager with deterministic time."""
    fake_time = {"t": 1000.0}

    def time_fn():
        return fake_time["t"]

    lm = InMemoryLockManager(time_fn=time_fn)
    
    # acquire lock first time
    assert lm.acquire_lock("lock-1", "ownerA", ttl_seconds=10) is True
    
    # cannot acquire while held
    assert lm.acquire_lock("lock-1", "ownerB", ttl_seconds=10) is False
    
    # advance time beyond ttl -> lock expires
    fake_time["t"] += 11
    assert lm.acquire_lock("lock-1", "ownerB", ttl_seconds=10) is True
    
    # ownerB can release
    assert lm.release_lock("lock-1", "ownerB") is True
    
    # releasing nonexistent lock returns False
    assert lm.release_lock("lock-1", "ownerB") is False


def test_inmemory_lock_manager_is_locked():
    """Test is_locked method."""
    fake_time = {"t": 2000.0}
    lm = InMemoryLockManager(time_fn=lambda: fake_time["t"])
    
    assert lm.is_locked("lock-2") is False
    
    lm.acquire_lock("lock-2", "owner1", ttl_seconds=5)
    assert lm.is_locked("lock-2") is True
    
    # Advance past TTL
    fake_time["t"] += 6
    assert lm.is_locked("lock-2") is False


def test_inmemory_lock_manager_get_owner():
    """Test get_owner method."""
    fake_time = {"t": 3000.0}
    lm = InMemoryLockManager(time_fn=lambda: fake_time["t"])
    
    assert lm.get_owner("lock-3") is None
    
    lm.acquire_lock("lock-3", "alice", ttl_seconds=10)
    assert lm.get_owner("lock-3") == "alice"
    
    # Advance past TTL
    fake_time["t"] += 11
    assert lm.get_owner("lock-3") is None
