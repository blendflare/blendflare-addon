"""Simple query cache with TTL."""
import time
import threading
from typing import Any, Optional, Dict


class QueryCache:
    """Thread-safe query cache with TTL-based expiration."""

    def __init__(self, ttl: float = 300.0):
        self._cache: Dict[str, tuple[Any, float]] = {}  # key -> (data, timestamp)
        self._ttl = ttl
        self._lock = threading.Lock()

    def _make_key(self, *args) -> str:
        """Generate cache key from arguments."""
        return ":".join(str(a) for a in args)

    def get(self, *args) -> Optional[Any]:
        """Get cached data if fresh, None otherwise."""
        key = self._make_key(*args)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            data, timestamp = entry
            if (time.time() - timestamp) > self._ttl:
                del self._cache[key]
                return None
            return data

    def set(self, data: Any, *args) -> None:
        """Store data in cache."""
        key = self._make_key(*args)
        with self._lock:
            self._cache[key] = (data, time.time())

    def invalidate(self, *args) -> None:
        """Remove specific cache entry."""
        key = self._make_key(*args)
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()


# Global singleton
_cache: Optional[QueryCache] = None


def get_cache(ttl: float = 300.0) -> QueryCache:
    """Get or create global cache instance."""
    global _cache
    if _cache is None:
        _cache = QueryCache(ttl=ttl)
    return _cache


def reset_cache() -> None:
    """Reset global cache."""
    global _cache
    if _cache is not None:
        _cache.clear()
        _cache = None
