from src.lib.firestore_lock import FirestoreLockManager
import time


class MockDoc:
    def __init__(self, storage, doc_id):
        self._storage = storage
        self._id = doc_id

    def create(self, data):
        if self._id in self._storage:
            raise Exception("AlreadyExists")
        self._storage[self._id] = data.copy()

    def set(self, data):
        self._storage[self._id] = data.copy()

    def get(self):
        class R:
            def __init__(self, data):
                self._data = data

            def to_dict(self):
                return self._data.copy() if self._data is not None else None

        return R(self._storage.get(self._id))

    def delete(self):
        if self._id in self._storage:
            del self._storage[self._id]


class MockCollection:
    def __init__(self, storage):
        self._storage = storage

    def document(self, doc_id):
        return MockDoc(self._storage, doc_id)


class MockClient:
    def __init__(self):
        self._storage = {}

    def collection(self, name):
        return MockCollection(self._storage)


def test_firestore_lock_manager_fallback_when_no_client():
    # if no client provided, manager should behave like in-memory lock
    mgr = FirestoreLockManager(client=None)
    assert mgr.acquire_lock("l1", "a", 5) is True
    assert mgr.acquire_lock("l1", "b", 5) is False


def test_firestore_lock_manager_with_mock_client():
    client = MockClient()
    # deterministic time
    t = [1000]

    def time_fn():
        return t[0]

    mgr = FirestoreLockManager(client=client, time_fn=time_fn)

    assert mgr.acquire_lock("lock-1", "ownerA", ttl_seconds=10) is True
    # cannot acquire while held
    assert mgr.acquire_lock("lock-1", "ownerB", ttl_seconds=10) is False

    # advance time beyond ttl
    t[0] += 11
    assert mgr.acquire_lock("lock-1", "ownerB", ttl_seconds=10) is True

    # ownerB can release
    assert mgr.release_lock("lock-1", "ownerB") is True

    # after release it's not locked
    assert mgr.is_locked("lock-1") is False
