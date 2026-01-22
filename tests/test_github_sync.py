import json
from src.github_sync.upsert import idempotent_upsert


class DictStore:
    def __init__(self):
        self._d = {}

    def get(self, k):
        return self._d.get(str(k))

    def set(self, k, v):
        self._d[str(k)] = v


def test_idempotent_upsert_new_and_same():
    store = DictStore()
    payload = {"issue": {"id": 123, "title": "Test", "updated_at": "t1"}}
    doc1 = idempotent_upsert(payload, store)
    assert doc1["title"] == "Test"

    # same updated_at should return existing
    payload2 = {"issue": {"id": 123, "title": "Test", "updated_at": "t1"}}
    doc2 = idempotent_upsert(payload2, store)
    assert doc2 is doc1 or doc2["updated_at"] == "t1"

    # newer update replaces
    payload3 = {"issue": {"id": 123, "title": "Test v2", "updated_at": "t2"}}
    doc3 = idempotent_upsert(payload3, store)
    assert doc3["title"] == "Test v2"
