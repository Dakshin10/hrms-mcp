import hashlib
import time


class QueryCache:
    def __init__(self, ttl_seconds=300):
        self._cache = {}  # key -> (result_dict, timestamp)
        self._ttl = ttl_seconds

    def _make_key(self, question: str) -> str:
        # Normalize: lowercase, strip, collapse multiple spaces to a single space
        normalized = " ".join(question.lower().split())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get(self, question: str) -> dict | None:
        key = self._make_key(question)
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                return result
            # Clean up expired entry
            del self._cache[key]
        return None

    def set(self, question: str, result: dict):
        key = self._make_key(question)
        self._cache[key] = (result, time.time())

    def invalidate_all(self):
        self._cache.clear()

    def stats(self) -> dict:
        return {"cached_queries": len(self._cache)}
