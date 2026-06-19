import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from src.mcp_server.tools.hr.hr_insights_handler import HRInsightsHandler


class TestHRInsightsHandler(unittest.TestCase):
    def setUp(self):
        self.handler = HRInsightsHandler()
        # Mock analytics classes
        self.handler.kpi = MagicMock()
        self.handler.timesheet = MagicMock()
        self.handler.employee = MagicMock()

    @patch("src.mcp_server.tools.hr.hr_insights_handler.generate_answer", new_callable=AsyncMock)
    async def async_test_route_top_performers(self, mock_gen_answer):
        self.handler.kpi.top_performers = AsyncMock(return_value=[{"name": "Alice"}])
        mock_gen_answer.return_value = "Top performers summary"

        res = await self.handler.handle("Show me top performers for 2026")
        
        self.assertEqual(res, "Top performers summary")
        # Check that year=2026 was parsed and passed correctly
        self.handler.kpi.top_performers.assert_called_once_with(limit=10, year=2026, month=None)
        mock_gen_answer.assert_called_once_with("Show me top performers for 2026", "kpi.top_performers", [{"name": "Alice"}])

    def test_route_top_performers(self):
        import asyncio
        asyncio.run(self.async_test_route_top_performers())

    @patch("src.mcp_server.tools.hr.hr_insights_handler.generate_answer", new_callable=AsyncMock)
    async def async_test_route_star_employees(self, mock_gen_answer):
        self.handler.kpi.top_performers = AsyncMock(return_value=[])
        mock_gen_answer.return_value = "No stars in April"

        res = await self.handler.handle("Who are star employees in April?")
        
        self.assertEqual(res, "No stars in April")
        # Check that month=4 (April) was parsed and passed correctly to top_performers under new router
        self.handler.kpi.top_performers.assert_called_once_with(limit=10, year=None, month=4)

    def test_route_star_employees(self):
        import asyncio
        asyncio.run(self.async_test_route_star_employees())


if __name__ == "__main__":
    unittest.main()
