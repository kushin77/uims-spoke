from typing import Optional, Dict, Any
from src.github_sync.upsert import idempotent_upsert
from src.lib.issue_state import IssueStateManager


def process_github_event(
    event: Dict[str, Any],
    firestore_client: Optional[object] = None,
    pubsub_publisher: Optional[object] = None,
) -> Dict[str, Any]:
    """Process a GitHub webhook event: perform idempotent upsert and emit pubsub message.

    - `event` is the parsed webhook payload (expects `id` and `issue` keys for this helper).
    - `firestore_client` if provided is passed to `IssueStateManager` for persistence; otherwise in-memory.
    - `pubsub_publisher` if provided should have a `publish(topic, data)` method.

    Returns a result dict with keys: `upserted` (bool) and `published` (bool).
    """
    issue = event.get("issue") or {}
    issue_id = str(issue.get("id") or issue.get("number") or event.get("id"))

    # perform idempotent upsert into primary store (this function is generic)
    # pass through firestore_client as the store when available
    # idempotent_upsert expects a `store` with get(id)/set(id, value).
    # If no firestore_client is provided, use a simple in-memory store adapter.
    class _InMemoryStore:
        def __init__(self):
            self._s = {}

        def get(self, id_):
            return self._s.get(id_)

        def set(self, id_, value):
            self._s[id_] = value

    store = firestore_client if firestore_client is not None else _InMemoryStore()
    try:
        upserted = idempotent_upsert(event, store)
    except TypeError:
        upserted = idempotent_upsert(event)

    # write canonical issue_state using IssueStateManager (best-effort)
    ism = IssueStateManager(client=firestore_client)
    try:
        # convert minimal fields
        state = ism.get(issue_id)
        if state is None:
            from src.lib.firestore_schema import IssueState

            state = IssueState(
                issue_id=issue_id,
                current_status=issue.get("state", "open"),
                score=0.0,
                version=1,
                assignee=issue.get("assignee", {}).get("login")
                if issue.get("assignee")
                else None,
                project=None,
            )
        else:
            # update fields conservatively
            state.current_status = issue.get("state", state.current_status)
            state.assignee = (
                issue.get("assignee", {}).get("login")
                if issue.get("assignee")
                else state.assignee
            )
            state.version = (state.version or 0) + 1
        ism.upsert(state)
    except Exception:
        # ignore persistence errors here; keep going
        pass

    published = False
    if pubsub_publisher is not None:
        try:
            # topic name is conventional
            pubsub_publisher.publish(
                "issue-events", {"issue_id": issue_id, "action": event.get("action")}
            )
            published = True
        except Exception:
            published = False

    return {"upserted": bool(upserted), "published": published}


__all__ = ["process_github_event"]
