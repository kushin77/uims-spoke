from src.lib.issue_state import IssueStateManager
from src.lib.firestore_schema import IssueState


def test_issue_state_upsert_and_get():
    mgr = IssueStateManager(client=None)
    s = IssueState(
        issue_id="I-1", current_status="open", score=0.2, version=1, assignee=None
    )
    mgr.upsert(s)
    got = mgr.get("I-1")
    assert got is not None
    assert got.issue_id == "I-1"
    assert got.score == 0.2


def test_claim_issue_in_memory():
    mgr = IssueStateManager(client=None)
    # create an issue
    s = IssueState(
        issue_id="I-2", current_status="open", score=0.0, version=0, assignee=None
    )
    mgr.upsert(s)

    ok = mgr.claim_issue("I-2", "bob", ttl_seconds=5)
    assert ok is True
    got = mgr.get("I-2")
    assert got.assignee == "bob"

    # trying to claim as someone else should fail
    ok2 = mgr.claim_issue("I-2", "alice", ttl_seconds=5)
    assert ok2 is False
