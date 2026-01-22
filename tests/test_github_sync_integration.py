from src.github_sync.integration import process_github_event


class MockPubSub:
    def __init__(self):
        self.published = []

    def publish(self, topic, data):
        self.published.append((topic, data))


def test_process_github_event_in_memory_pubsub():
    event = {"action": "opened", "issue": {"id": 42, "state": "open", "assignee": None}}
    pub = MockPubSub()
    res = process_github_event(event, firestore_client=None, pubsub_publisher=pub)
    assert res["upserted"] is True
    assert res["published"] is True
    assert len(pub.published) == 1
    topic, data = pub.published[0]
    assert topic == "issue-events"
    assert data["issue_id"] == "42"
