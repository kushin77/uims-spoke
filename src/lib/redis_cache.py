import time
from typing import Optional


class InMemoryCache:
    def __init__(self, time_fn=None):
        self._time = time_fn or time.time
        self._store = {}

    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None):
        expiry = None
        if ttl_seconds:
            expiry = int(self._time()) + int(ttl_seconds)
        self._store[key] = (value, expiry)

    def get(self, key: str) -> Optional[str]:
        v = self._store.get(key)
        if not v:
            return None
        value, expiry = v
        if expiry and expiry <= int(self._time()):
            del self._store[key]
            return None
        return value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class RedisCache:
    """Wrapper around a redis client. If `client` is None, uses InMemoryCache."""

    def __init__(self, client: Optional[object] = None, time_fn=None):
        self._client = client
        self._fallback = InMemoryCache(time_fn=time_fn) if client is None else None
        self._time = time_fn or time.time

    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None):
        if self._fallback:
            return self._fallback.set(key, value, ttl_seconds)
        # Attempt to use redis-py `set` with ex
        try:
            if ttl_seconds:
                return self._client.set(key, value, ex=int(ttl_seconds))
            return self._client.set(key, value)
        except Exception:
            # Best-effort fallback
            return self._fallback.set(key, value, ttl_seconds)

    def get(self, key: str) -> Optional[str]:
        if self._fallback:
            return self._fallback.get(key)
        try:
            v = self._client.get(key)
            # redis-py returns bytes
            if v is None:
                return None
            if isinstance(v, bytes):
                return v.decode("utf-8")
            return str(v)
        except Exception:
            return self._fallback.get(key)

    def delete(self, key: str) -> None:
        if self._fallback:
            return self._fallback.delete(key)
        try:
            return self._client.delete(key)
        except Exception:
            return self._fallback.delete(key)
