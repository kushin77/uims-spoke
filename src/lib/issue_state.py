from typing import Optional, List
from dataclasses import asdict
from .firestore_schema import IssueState
from .firestore_lock import FirestoreLockManager


class IssueStateManager:
    """Manages issue_state documents using a Firestore-like client or in-memory fallback."""

    def __init__(
        self,
        client: Optional[object] = None,
        collection: str = "issue_state",
        time_fn=None,
    ):
        self._client = client
        self._collection = collection
        self._lock_mgr = FirestoreLockManager(
            client=client, collection="locks", time_fn=time_fn
        )
        # in-memory fallback store for tests
        if client is None:
            self._store = {}
        else:
            self._store = None

    def _doc_ref(self, issue_id: str):
        return self._client.collection(self._collection).document(issue_id)

    def get(self, issue_id: str) -> Optional[IssueState]:
        if self._store is not None:
            data = self._store.get(issue_id)
            if data is None:
                return None
            return IssueState(**data)

        doc = self._doc_ref(issue_id).get()
        data = getattr(doc, "to_dict", lambda: None)() or {}
        if not data:
            return None
        return IssueState(**data)

    def upsert(self, state: IssueState) -> None:
        if self._store is not None:
            self._store[state.issue_id] = asdict(state)
            return

        self._doc_ref(state.issue_id).set(asdict(state))

    def claim_issue(self, issue_id: str, owner: str, ttl_seconds: int = 30) -> bool:
        """Attempt to claim an issue for `owner`. Uses locks to avoid races.

        Returns True if claim succeeded, False otherwise.
        """
        locked = self._lock_mgr.acquire_lock(issue_id, owner, ttl_seconds)
        if not locked:
            return False

        try:
            state = self.get(issue_id)
            if state is None:
                # create minimal state
                state = IssueState(
                    issue_id=issue_id,
                    current_status="open",
                    score=0.0,
                    version=0,
                    assignee=owner,
                )
            else:
                # if already assigned, fail
                if state.assignee and state.assignee != owner:
                    return False
                state.assignee = owner
                state.version = (state.version or 0) + 1

            self.upsert(state)
            return True
        finally:
            # release lock; best-effort
            try:
                self._lock_mgr.release_lock(issue_id, owner)
            except Exception:
                pass

    def list_unassigned(self, limit: int = 50) -> List[IssueState]:
        """List unassigned issues. For in-memory fallback use simple scan. For real Firestore client,
        this will attempt to run a query if supported; otherwise returns empty list.
        """
        if self._store is not None:
            out = []
            for data in self._store.values():
                if not data.get("assignee"):
                    out.append(IssueState(**data))
                    if len(out) >= limit:
                        break
            return out

        try:
            col = self._client.collection(self._collection)
            # rely on Firestore query API if available
            q = getattr(col, "where", None)
            if q is None:
                return []
            results = col.where("assignee", "==", None).limit(limit).stream()
            return [
                IssueState(**(getattr(r, "to_dict", lambda: {})() or {}))
                for r in results
            ]
        except Exception:
            return []


__all__ = ["IssueStateManager"]
