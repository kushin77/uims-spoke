from typing import Optional, Any
from src.github_sync.integration import process_github_event


def github_webhook(
    request: Any,
    firestore_client: Optional[object] = None,
    pubsub_publisher: Optional[object] = None,
):
    """Cloud Function / HTTP handler for GitHub webhooks.

    Expects a Flask-like `request` with `get_json()` method. Returns a tuple (body, status).
    This handler is intentionally simple and delegates processing to `process_github_event`.
    """
    try:
        payload = request.get_json(force=True)
    except Exception:
        return ("invalid json", 400)

    result = process_github_event(
        payload, firestore_client=firestore_client, pubsub_publisher=pubsub_publisher
    )
    return ({"ok": True, "result": result}, 200)


__all__ = ["github_webhook"]
