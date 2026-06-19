import unittest
import time
from src.services.ai.query_cache import QueryCache


class TestQueryCache(unittest.TestCase):
    def setUp(self):
        self.cache = QueryCache(ttl_seconds=1)

    def test_cache_miss(self):
        self.assertIsNone(self.cache.get("nonexistent question"))

    def test_cache_hit(self):
        result = {"generated_sql": "SELECT 1", "results": [{"val": 1}]}
        self.cache.set("how many employees", result)
        self.assertEqual(self.cache.get("how many employees"), result)

    def test_normalization_hits_same_key(self):
        result = {"generated_sql": "SELECT *", "results": []}
        self.cache.set("How many employees", result)
        
        # Test lower casing, stripping, collapsing spaces
        self.assertEqual(self.cache.get("how many employees"), result)
        self.assertEqual(self.cache.get("  HOW   MANY   EMPLOYEES  "), result)

    def test_cache_expiry(self):
        result = {"val": "test"}
        self.cache.set("query to expire", result)
        self.assertEqual(self.cache.get("query to expire"), result)
        
        # Sleep for longer than TTL (1s)
        time.sleep(1.1)
        self.assertIsNone(self.cache.get("query to expire"))

    def test_invalidate_all(self):
        result = {"val": "test"}
        self.cache.set("q1", result)
        self.cache.set("q2", result)
        self.assertEqual(self.cache.stats()["cached_queries"], 2)
        
        self.cache.invalidate_all()
        self.assertEqual(self.cache.stats()["cached_queries"], 0)
        self.assertIsNone(self.cache.get("q1"))


if __name__ == "__main__":
    unittest.main()
