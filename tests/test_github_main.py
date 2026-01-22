import time


class _MockRequest:
    def __init__(self, payload):
        self._payload = payload

    def get_json(self, force=False):
        return self._payload


class MockPubSub:
    def __init__(self):
        self.published = []

    def publish(self, topic, data):
        self.published.append((topic, data))


def test_main_success(monkeypatch):
    from src.github_sync.main import main

    req = _MockRequest({"action": "opened", "issue": {"id": 99}})
    pub = MockPubSub()

    # avoid sleeping during tests
    monkeypatch.setattr(time, "sleep", lambda s: None)

    body, status = main(req, firestore_client=None, pubsub_publisher=pub)
    assert status == 200
    assert body["ok"] is True
    assert body["result"]["published"] is True
    assert len(pub.published) == 1
