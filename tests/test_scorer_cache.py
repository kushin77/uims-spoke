from time import sleep
from src.smart_selector.scorer import composite_score
from src.smart_selector.cache import cached_composite_score
from src.lib.redis_cache import InMemoryCache


def test_cached_score():
    issue = {"issue_id": "I-200", "days_open": 10, "priority_level": 1, "cost_impact": 500, "blocker_count": 0, "team_velocity": 0.6}
    cache = InMemoryCache()
    s1 = cached_composite_score(issue, cache, ttl_seconds=1)
    s2 = cached_composite_score(issue, cache, ttl_seconds=1)
    assert s1 == s2
    sleep(1.1)
    s3 = cached_composite_score(issue, cache, ttl_seconds=1)
    assert s3 == composite_score(issue)
