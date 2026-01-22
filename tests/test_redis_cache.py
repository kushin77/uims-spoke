import time
from src.lib.redis_cache import RedisCache, InMemoryCache


def test_inmemory_cache_ttl():
    t0 = [int(time.time())]

    def time_fn():
        return t0[0]

    c = InMemoryCache(time_fn=time_fn)
    c.set("k", "v", ttl_seconds=2)
    assert c.get("k") == "v"
    t0[0] += 3
    assert c.get("k") is None


def test_redis_cache_fallback():
    rc = RedisCache(client=None)
    rc.set("a", "1", ttl_seconds=1)
    assert rc.get("a") == "1"
    time.sleep(1.1)
    assert rc.get("a") is None
