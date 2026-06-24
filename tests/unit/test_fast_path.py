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


from src.agent.fast_path import fast_path_router

class TestNewFastPath(unittest.TestCase):
    @patch("src.agent.fast_path.list_tables", new_callable=AsyncMock)
    def test_new_fast_path_list_tables(self, mock_list):
        mock_list.return_value = ["employees", "timesheets"]
        import asyncio
        res = asyncio.run(fast_path_router("show all tables"))
        self.assertIsNotNone(res)
        self.assertIn("Database Tables", res["answer"])
        self.assertEqual(res["tools_used"], ["list_tables"])

    @patch("src.agent.fast_path.list_tables", new_callable=AsyncMock)
    @patch("src.agent.fast_path.execute_sql", new_callable=AsyncMock)
    def test_new_fast_path_smart_sql(self, mock_exec, mock_list):
        mock_list.return_value = ["employee_kpis"]
        mock_exec.return_value = [{"id": 1, "score": 90}]
        import asyncio
        res = asyncio.run(fast_path_router("display all data from employee_kpis"))
        self.assertIsNotNone(res)
        self.assertIn("Query Result", res["answer"])
        self.assertEqual(res["tools_used"], ["execute_sql"])
        mock_exec.assert_called_once_with("SELECT * FROM employee_kpis LIMIT 100;")


if __name__ == "__main__":
    unittest.main()
