from typing import Optional
import time

from .firestore_schema import InMemoryLockManager


class FirestoreLockManager:
    """Emulator-safe Firestore lock manager with optional transactional support.

    Behavior:
    - If `client` is None, fall back to an in-memory implementation.
    - If the Firestore-like client supports transactions via `client.transaction()` we
      attempt to perform atomic acquire/release operations via the transaction object.
    - Lock documents have shape: { owner: str, expiry: int } where expiry is epoch sec.
    """

    def __init__(self, client: Optional[object] = None, collection: str = "locks", time_fn=None):
        self._client = client
        self._collection = collection
        self._time_fn = time_fn or time.time
        if client is None:
            self._fallback = InMemoryLockManager(time_fn=time_fn)
        else:
            self._fallback = None

    def _now(self) -> float:
        return self._time_fn()

    def _get_doc_ref(self, lock_id: str):
        return self._client.collection(self._collection).document(lock_id)

    def _supports_transactions(self) -> bool:
        return self._client is not None and callable(getattr(self._client, "transaction", None))

    def acquire_lock(self, lock_id: str, owner: str, ttl_seconds: int, retry_seconds: float = 0.0, timeout_seconds: float = 0.0) -> bool:
        """Try to acquire a lock. If `retry_seconds` > 0, keep retrying until timeout_seconds.

        Returns True if lock acquired, False otherwise.
        """
        if self._fallback:
            return self._fallback.acquire_lock(lock_id, owner, ttl_seconds)

        deadline = self._now() + float(timeout_seconds) if timeout_seconds and timeout_seconds > 0 else None
        while True:
            now = int(self._now())
            expiry = now + int(ttl_seconds)

            # Try transactional path first if supported
            if self._supports_transactions():
                try:
                    txn = self._client.transaction()
                    doc_ref = self._get_doc_ref(lock_id)
                    # Attempt to get snapshot inside transaction
                    try:
                        snapshot = doc_ref.get(transaction=txn)
                        data = snapshot.to_dict() or {}
                    except Exception:
                        # fallback to non-transactional get
                        data = getattr(doc_ref.get(), "to_dict", lambda: None)() or {}
                    existing_expiry = int(data.get("expiry", 0))
                    if existing_expiry <= now:
                        # set within transaction if supported
                        try:
                            txn.set(doc_ref, {"owner": owner, "expiry": expiry})
                            return True
                        except Exception:
                            # try doc_ref.set as last resort
                            doc_ref.set({"owner": owner, "expiry": expiry})
                            return True
                    # otherwise locked
                except Exception:
                    # transaction step failed; fall through to non-transactional path
                    pass

            # Non-transactional / generic path
            doc_ref = self._get_doc_ref(lock_id)
            try:
                # Prefer create semantics if available to avoid extra race window
                doc_ref.create({"owner": owner, "expiry": expiry})
                return True
            except Exception:
                try:
                    data = doc_ref.get().to_dict() or {}
                except Exception:
                    data = getattr(doc_ref.get(), "to_dict", lambda: None)() or {}
                existing_expiry = int(data.get("expiry", 0))
                if existing_expiry <= now:
                    try:
                        doc_ref.set({"owner": owner, "expiry": expiry})
                        return True
                    except Exception:
                        return False
                # otherwise locked

            if deadline and self._now() > deadline:
                return False
            if retry_seconds and retry_seconds > 0:
                time.sleep(retry_seconds)
                continue
            return False

    def refresh_lock(self, lock_id: str, owner: str, ttl_seconds: int) -> bool:
        """Extend the lock TTL if owner matches and lock is held."""
        if self._fallback:
            return self._fallback.refresh_lock(lock_id, owner, ttl_seconds)
        doc_ref = self._get_doc_ref(lock_id)
        try:
            data = doc_ref.get().to_dict() or {}
        except Exception:
            data = getattr(doc_ref.get(), "to_dict", lambda: None)() or {}
        existing_owner = data.get("owner")
        if existing_owner != owner:
            return False
        expiry = int(self._now()) + int(ttl_seconds)
        try:
            doc_ref.set({"owner": owner, "expiry": expiry})
            return True
        except Exception:
            return False

    def release_lock(self, lock_id: str, owner: str) -> bool:
        if self._fallback:
            return self._fallback.release_lock(lock_id, owner)

        # Transactional release when supported
        if self._supports_transactions():
            try:
                txn = self._client.transaction()
                doc_ref = self._get_doc_ref(lock_id)
                try:
                    snapshot = doc_ref.get(transaction=txn)
                    data = snapshot.to_dict() or {}
                except Exception:
                    data = getattr(doc_ref.get(), "to_dict", lambda: None)() or {}
                existing_owner = data.get("owner")
                if existing_owner != owner:
                    return False
                try:
                    txn.delete(doc_ref)
                    return True
                except Exception:
                    # fallback to delete
                    doc_ref.delete()
                    return True
            except Exception:
                # fall back to non-transactional path
                pass

        doc_ref = self._get_doc_ref(lock_id)
        try:
            data = doc_ref.get().to_dict() or {}
        except Exception:
            data = getattr(doc_ref.get(), "to_dict", lambda: None)() or {}
        existing_owner = data.get("owner")
        if existing_owner != owner:
            return False
        try:
            doc_ref.delete()
            return True
        except Exception:
            return False

    def is_locked(self, lock_id: str) -> bool:
        if self._fallback:
            return self._fallback.is_locked(lock_id)
        doc_ref = self._get_doc_ref(lock_id)
        try:
            data = doc_ref.get().to_dict() or {}
        except Exception:
            data = getattr(doc_ref.get(), "to_dict", lambda: None)() or {}
        expiry = int(data.get("expiry", 0))
        return expiry > int(self._now())

    def get_owner(self, lock_id: str) -> Optional[str]:
        if self._fallback:
            return self._fallback.get_owner(lock_id)
        doc_ref = self._get_doc_ref(lock_id)
        try:
            data = doc_ref.get().to_dict() or {}
        except Exception:
            data = getattr(doc_ref.get(), "to_dict", lambda: None)() or {}
        expiry = int(data.get("expiry", 0))
        if expiry <= int(self._now()):
            return None
        return data.get("owner")


__all__ = ["FirestoreLockManager"]
