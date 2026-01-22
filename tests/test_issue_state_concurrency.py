import threading
from src.lib.issue_state import IssueStateManager
from src.lib.firestore_schema import IssueState


def _attempt_claim(mgr, issue_id, owner, results, idx):
    ok = mgr.claim_issue(issue_id, owner, ttl_seconds=2)
    results[idx] = ok


def test_concurrent_claims():
    mgr = IssueStateManager(client=None)
    s = IssueState(issue_id="I-100", current_status="open", score=0.0, version=0, assignee=None)
    mgr.upsert(s)

    results = [None] * 5
    threads = []
    owners = [f"user{i}" for i in range(5)]
    for i, owner in enumerate(owners):
        t = threading.Thread(target=_attempt_claim, args=(mgr, "I-100", owner, results, i))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Exactly one thread should have succeeded
    assert sum(1 for r in results if r) == 1
