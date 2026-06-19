import unittest
from unittest.mock import AsyncMock, patch
from src.services.ai.fast_path import FastPathHandler


class TestFastPath(unittest.TestCase):
    def setUp(self):
        self.handler = FastPathHandler()

    async def async_test_matches_count_employees(self):
        with patch.object(self.handler, 'count_employees', new_callable=AsyncMock) as mock_count:
            mock_count.return_value = {"answer": "Count triggered"}
            res = await self.handler.try_handle("how many employees are there?")
            self.assertEqual(res, {"answer": "Count triggered"})
            mock_count.assert_called_once()

    def test_matches_count_employees(self):
        import asyncio
        asyncio.run(self.async_test_matches_count_employees())

    async def async_test_matches_list_tables(self):
        with patch.object(self.handler, 'list_tables', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = {"answer": "Tables triggered"}
            res = await self.handler.try_handle("list tables")
            self.assertEqual(res, {"answer": "Tables triggered"})
            mock_list.assert_called_once()

    def test_matches_list_tables(self):
        import asyncio
        asyncio.run(self.async_test_matches_list_tables())

    async def async_test_no_match_returns_none(self):
        res = await self.handler.try_handle("who has the highest kpi score?")
        self.assertIsNone(res)

    def test_no_match_returns_none(self):
        import asyncio
        asyncio.run(self.async_test_no_match_returns_none())


if __name__ == "__main__":
    unittest.main()
