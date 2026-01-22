from src.lib.firestore_schema import InMemoryLockManager, IssueState


def test_issue_state_dataclass():
    s = IssueState(
        issue_id="ISSUE-1",
        current_status="open",
        score=0.5,
        version=1,
        assignee="alice",
    )
    assert s.issue_id == "ISSUE-1"
    assert s.current_status == "open"
    assert s.score == 0.5
    assert s.assignee == "alice"


def test_inmemory_lock_manager_acquire_and_release():
    # deterministic fake time
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
