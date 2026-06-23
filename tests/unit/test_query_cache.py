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

    def test_cache_metrics(self):
        # Initial stats
        stats = self.cache.stats()
        self.assertEqual(stats["total_queries"], 0)
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["hit_rate"], 0.0)

        # 1. Miss
        self.assertIsNone(self.cache.get("q1"))
        stats = self.cache.stats()
        self.assertEqual(stats["total_queries"], 1)
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 0.0)

        # 2. Set and Hit
        result = {"val": "test"}
        self.cache.set("q1", result)
        self.assertEqual(self.cache.get("q1"), result)
        stats = self.cache.stats()
        self.assertEqual(stats["total_queries"], 2)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 50.0)

        # 3. Expiry is a miss
        time.sleep(1.1)
        self.assertIsNone(self.cache.get("q1"))
        stats = self.cache.stats()
        self.assertEqual(stats["total_queries"], 3)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 2)
        self.assertAlmostEqual(stats["hit_rate"], 33.3333333, places=2)


if __name__ == "__main__":
    unittest.main()
