import time
from typing import Any, Optional, Tuple
from src.github_sync.handler import github_webhook


def main(
    request: Any,
    firestore_client: Optional[object] = None,
    pubsub_publisher: Optional[object] = None,
) -> Tuple[dict, int]:
    """GCF-compatible HTTP entrypoint that delegates to `github_webhook`.

    Implements a conservative retry loop with exponential backoff for transient errors.
    Returns a tuple (body, status_code).
    """
    max_retries = 3
    backoff = 0.25
    for attempt in range(1, max_retries + 1):
        try:
            body, status = github_webhook(
                request,
                firestore_client=firestore_client,
                pubsub_publisher=pubsub_publisher,
            )
            return body, status
        except Exception as e:
            if attempt == max_retries:
                return {"ok": False, "error": str(e)}, 500
            time.sleep(backoff)
            backoff *= 2


__all__ = ["main"]
