from typing import Optional
from .scorer import composite_score


def cached_composite_score(issue: dict, cache, ttl_seconds: int = 300, weights: Optional[dict] = None):
    key = f"score:{issue.get('issue_id') or issue.get('id') or issue.get('number')}"
    val = cache.get(key)
    if val is not None:
        try:
            return float(val)
        except Exception:
            pass
    s = composite_score(issue, weights)
    cache.set(key, str(s), ttl_seconds=ttl_seconds)
    return s
