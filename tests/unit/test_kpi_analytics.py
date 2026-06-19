import unittest
from unittest.mock import AsyncMock, MagicMock
from src.services.analytics.kpi_analytics import KPIAnalytics


class TestKPIAnalytics(unittest.TestCase):
    def setUp(self):
        self.mock_qs = MagicMock()
        self.analytics = KPIAnalytics(self.mock_qs)

    async def async_test_top_performers(self):
        expected = [
            {"employee_id": "EMP1", "employee_name": "Alice", "achievement": 95.0},
            {"employee_id": "EMP2", "employee_name": "Bob", "achievement": 85.0}
        ]
        self.mock_qs.execute_query = AsyncMock(return_value=expected)
        res = await self.analytics.top_performers(limit=2)
        self.assertEqual(res, expected)
        self.mock_qs.execute_query.assert_called_once()

    def test_top_performers(self):
        import asyncio
        asyncio.run(self.async_test_top_performers())

    async def async_test_bottom_performers(self):
        expected = [
            {"employee_id": "EMP3", "employee_name": "Charlie", "achievement": 60.0}
        ]
        self.mock_qs.execute_query = AsyncMock(return_value=expected)
        res = await self.analytics.bottom_performers(threshold=70)
        self.assertEqual(res, expected)

    def test_bottom_performers(self):
        import asyncio
        asyncio.run(self.async_test_bottom_performers())

    async def async_test_kpi_distribution(self):
        db_return = [{
            "band_0_50": 1,
            "band_50_70": 3,
            "band_70_85": 10,
            "band_85_100": 5
        }]
        self.mock_qs.execute_query = AsyncMock(return_value=db_return)
        res = await self.analytics.kpi_distribution()
        
        expected_bands = [
            {"band": "0-50%", "count": 1},
            {"band": "50-70%", "count": 3},
            {"band": "70-85%", "count": 10},
            {"band": "85-100%", "count": 5}
        ]
        self.assertEqual(res, expected_bands)

    def test_kpi_distribution(self):
        import asyncio
        asyncio.run(self.async_test_kpi_distribution())

    async def async_test_db_exception_returns_empty(self):
        self.mock_qs.execute_query = AsyncMock(side_effect=Exception("Database error"))
        res = await self.analytics.top_performers()
        self.assertEqual(res, [])

    def test_db_exception_returns_empty(self):
        import asyncio
        asyncio.run(self.async_test_db_exception_returns_empty())


if __name__ == "__main__":
    unittest.main()
