import time
from src.lib.firestore_lock import FirestoreLockManager


class FakeSnapshot:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeDocRef:
    def __init__(self, store, key):
        self._store = store
        self._key = key

    def get(self, transaction=None):
        # transaction param ignored in this fake implementation
        return FakeSnapshot(self._store.get(self._key))

    def create(self, data):
        if self._key in self._store:
            raise Exception("Already exists")
        self._store[self._key] = dict(data)

    def set(self, data):
        self._store[self._key] = dict(data)

    def delete(self):
        if self._key in self._store:
            del self._store[self._key]


class FakeCollection:
    def __init__(self, store):
        self._store = store

    def document(self, doc_id):
        return FakeDocRef(self._store, doc_id)


class FakeTransaction:
    def __init__(self, client):
        self._client = client

    def set(self, doc_ref, data):
        # immediate for our fake
        doc_ref.set(data)

    def delete(self, doc_ref):
        doc_ref.delete()


class FakeClient:
    def __init__(self, store=None):
        self._store = store or {}

    def collection(self, name):
        return FakeCollection(self._store)

    def transaction(self):
        return FakeTransaction(self)


def test_transactional_acquire_and_release():
    now = int(time.time())
    store = {"lock-1": {"owner": "alice", "expiry": now - 10}}  # expired
    client = FakeClient(store=store)

    mgr = FirestoreLockManager(client=client, collection="locks")

    # expired -> should acquire
    acquired = mgr.acquire_lock("lock-1", "bob", ttl_seconds=60)
    assert acquired is True
    assert mgr.get_owner("lock-1") == "bob"

    # refresh should extend
    assert mgr.refresh_lock("lock-1", "bob", ttl_seconds=30) is True

    # release by wrong owner should fail
    assert mgr.release_lock("lock-1", "alice") is False

    # release by correct owner should succeed
    assert mgr.release_lock("lock-1", "bob") is True
    assert mgr.get_owner("lock-1") is None


def test_non_transactional_create_path():
    client = FakeClient(store={})
    mgr = FirestoreLockManager(client=client, collection="locks")

    assert mgr.acquire_lock("new-lock", "carol", ttl_seconds=10) is True
    # acquiring again should fail
    assert mgr.acquire_lock("new-lock", "dave", ttl_seconds=10) is False

