import hashlib
import time


class QueryCache:
    def __init__(self, ttl_seconds=300):
        self._cache = {}  # key -> (result_dict, timestamp)
        self._ttl = ttl_seconds
        self._total_queries = 0
        self._hits = 0
        self._misses = 0

    def _make_key(self, question: str) -> str:
        # Normalize: lowercase, strip, collapse multiple spaces to a single space
        normalized = " ".join(question.lower().split())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get(self, question: str) -> dict | None:
        self._total_queries += 1
        key = self._make_key(question)
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                self._hits += 1
                return result
            # Clean up expired entry
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, question: str, result: dict):
        key = self._make_key(question)
        self._cache[key] = (result, time.time())

    def invalidate_all(self):
        self._cache.clear()

    def stats(self) -> dict:
        hit_rate = 0.0
        if self._total_queries > 0:
            hit_rate = (self._hits / self._total_queries) * 100.0
        return {
            "cached_queries": len(self._cache),
            "total_queries": self._total_queries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate
        }
