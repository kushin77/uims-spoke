"""Idempotent upsert helper for GitHub sync.

This is a lightweight, testable abstraction. Production will use Firestore client
with proper transactions and TTL-based deduplication. The interface below takes
an `issue_payload` dict and a `store` object implementing `get(id)`, `set(id, val)`.
"""

from typing import Dict, Any


def idempotent_upsert(issue_payload: Dict[str, Any], store) -> Dict[str, Any]:
    """Upsert the issue by GitHub `id` field. Returns stored document.

    store must implement get(id) and set(id, value) methods. This function
    ensures idempotency by checking existing record and updating only if
    `updated_at` differs.
    """
    gh_issue = issue_payload.get("issue") or {}
    gh_id = gh_issue.get("id")
    if gh_id is None:
        raise ValueError("missing issue.id")

    existing = store.get(gh_id)
    # For testable simplicity, we compare `updated_at` field.
    incoming_updated = gh_issue.get("updated_at")
    if existing:
        if incoming_updated and existing.get("updated_at") == incoming_updated:
            return existing
        # merge fields conservatively
        merged = {**existing, **gh_issue}
        store.set(gh_id, merged)
        return merged
    else:
        store.set(gh_id, gh_issue)
        return gh_issue
