import unittest
from unittest.mock import AsyncMock, MagicMock
from src.services.ai.schema_builder import SchemaBuilder


class TestSchemaBuilder(unittest.TestCase):
    def setUp(self):
        self.metadata_service = MagicMock()
        self.metadata_service.get_tables = AsyncMock(return_value=[
            {"name": "employees"},
            {"name": "timesheet_summary"}
        ])
        self.metadata_service.get_table_schema = AsyncMock(side_effect=lambda name: {
            "employees": [
                {"name": "employee_id", "type": "TEXT", "pk": 1, "notnull": 1},
                {"name": "first_name", "type": "TEXT", "pk": 0, "notnull": 0}
            ],
            "timesheet_summary": [
                {"name": "employee_id", "type": "TEXT", "pk": 1, "notnull": 1},
                {"name": "utilization_percentage", "type": "REAL", "pk": 0, "notnull": 0}
            ]
        }[name])
        
        self.builder = SchemaBuilder(self.metadata_service)

    async def async_test_cache_and_invalidation(self):
        # First call fetches from service
        schema = await self.builder.get_full_schema()
        self.assertIn("employees", schema)
        self.assertIn("timesheet_summary", schema)
        self.assertEqual(self.metadata_service.get_tables.call_count, 1)
        self.assertEqual(self.metadata_service.get_table_schema.call_count, 2)

        # Second call hits cache
        schema2 = await self.builder.get_full_schema()
        self.assertEqual(self.metadata_service.get_tables.call_count, 1)
        self.assertEqual(self.metadata_service.get_table_schema.call_count, 2)

        # Invalidate cache
        self.builder.invalidate()
        
        # Third call fetches from service again
        schema3 = await self.builder.get_full_schema()
        self.assertEqual(self.metadata_service.get_tables.call_count, 2)
        self.assertEqual(self.metadata_service.get_table_schema.call_count, 4)

    def test_cache_and_invalidation(self):
        import asyncio
        asyncio.run(self.async_test_cache_and_invalidation())

    async def async_test_subset_schema(self):
        schema = await self.builder.get_schema_for_tables(["employees"])
        self.assertIn("employees", schema)
        self.assertNotIn("timesheet_summary", schema)

    def test_subset_schema(self):
        import asyncio
        asyncio.run(self.async_test_subset_schema())

    def test_schema_formatting(self):
        mock_schema = {
            "employees": [
                {"name": "employee_id", "type": "TEXT", "pk": 1, "notnull": 1},
                {"name": "first_name", "type": "TEXT", "pk": 0, "notnull": 0}
            ]
        }
        formatted = self.builder.get_schema_as_prompt_string(mock_schema)
        self.assertIn("Table: employees", formatted)
        self.assertIn("- employee_id (TEXT) [PK] NOT NULL", formatted)
        self.assertIn("- first_name (TEXT)", formatted)


if __name__ == "__main__":
    unittest.main()
