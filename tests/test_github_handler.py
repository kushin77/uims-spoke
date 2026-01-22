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


def test_github_webhook_handler_basic():
    from src.github_sync.handler import github_webhook

    req = _MockRequest({"action": "opened", "issue": {"id": 7}})
    pub = MockPubSub()
    body, status = github_webhook(req, firestore_client=None, pubsub_publisher=pub)
    assert status == 200
    assert body["ok"] is True
    assert body["result"]["published"] is True
    assert len(pub.published) == 1
