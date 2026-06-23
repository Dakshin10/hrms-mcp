import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import os
from pathlib import Path

# Since importing server.py runs mcp.run() if run as __main__, but here it's imported as a module,
# it won't run mcp.run(). Let's import the tool functions.
from src.mcp_server.server import (
    list_tables,
    describe_table,
    execute_sql,
    load_timesheets,
    hr_insights,
    cache_stats,
    ask_database,
    hr_agent,
    clear_session,
)


class TestMCPServerTools(unittest.TestCase):
    
    @patch("src.mcp_server.server.metadata_service")
    def test_list_tables_success(self, mock_meta):
        mock_meta.get_tables = AsyncMock(return_value=["employees", "timesheets"])
        import asyncio
        res = asyncio.run(list_tables())
        self.assertEqual(res, ["employees", "timesheets"])

    @patch("src.mcp_server.server.metadata_service")
    def test_list_tables_exception(self, mock_meta):
        mock_meta.get_tables = AsyncMock(side_effect=Exception("DB Error"))
        import asyncio
        res = asyncio.run(list_tables())
        self.assertEqual(res, {"error": "DB Error", "tool": "list_tables"})

    @patch("src.mcp_server.server.metadata_service")
    def test_describe_table_success(self, mock_meta):
        mock_meta.get_table_schema = AsyncMock(return_value={"id": "INTEGER"})
        import asyncio
        res = asyncio.run(describe_table("employees"))
        self.assertEqual(res, {"id": "INTEGER"})

    @patch("src.mcp_server.server.metadata_service")
    def test_describe_table_exception(self, mock_meta):
        mock_meta.get_table_schema = AsyncMock(side_effect=Exception("Schema Error"))
        import asyncio
        res = asyncio.run(describe_table("employees"))
        self.assertEqual(res, {"error": "Schema Error", "tool": "describe_table"})

    @patch("src.mcp_server.server.schema_builder")
    @patch("src.mcp_server.server.sql_validator")
    @patch("src.mcp_server.server.query_service")
    def test_execute_sql_success(self, mock_query, mock_val, mock_sb):
        mock_sb.get_full_schema = AsyncMock(return_value={})
        mock_query.execute_query = AsyncMock(return_value=[{"count": 1}])
        import asyncio
        res = asyncio.run(execute_sql("SELECT count(*) FROM employees"))
        self.assertEqual(res, [{"count": 1}])

    @patch("src.mcp_server.server.schema_builder")
    @patch("src.mcp_server.server.sql_validator")
    def test_execute_sql_validation_error(self, mock_val, mock_sb):
        mock_sb.get_full_schema = AsyncMock(return_value={})
        mock_val.validate.side_effect = Exception("Validation failed")
        import asyncio
        res = asyncio.run(execute_sql("DELETE FROM employees"))
        self.assertEqual(res, {"error": "Validation failed", "tool": "execute_sql"})

    @patch("src.mcp_server.server.timesheet_loader")
    def test_load_timesheets_path_validation_success(self, mock_loader):
        mock_loader.load_file = AsyncMock(return_value={
            "loaded": 5, "total_rows": 5, "file": "test.csv", "skipped": 0
        })
        import asyncio
        # Path inside ./data/imports
        res = asyncio.run(load_timesheets("data/imports/valid.csv"))
        self.assertIn("Loaded 5 of 5 rows from test.csv. Skipped 0 invalid rows.", res)

    def test_load_timesheets_path_validation_denied(self):
        import asyncio
        res = asyncio.run(load_timesheets("tests/unit/test_query_cache.py"))
        self.assertEqual(res["tool"], "load_timesheets")
        self.assertIn("Access denied", res["error"])

    @patch("src.mcp_server.server.hr_handler")
    def test_hr_insights_success(self, mock_hr):
        mock_hr.handle = AsyncMock(return_value="Answer from insights handler")
        import asyncio
        res = asyncio.run(hr_insights("Who is the top performer?"))
        self.assertEqual(res, "Answer from insights handler")

    @patch("src.mcp_server.server.hr_handler")
    def test_hr_insights_exception(self, mock_hr):
        mock_hr.handle = AsyncMock(side_effect=Exception("Insights error"))
        import asyncio
        res = asyncio.run(hr_insights("Who is the top performer?"))
        self.assertEqual(res, {"error": "Insights error", "tool": "hr_insights"})

    @patch("src.mcp_server.server.query_cache")
    def test_cache_stats_success(self, mock_cache):
        mock_cache.stats.return_value = {
            "cached_queries": 2,
            "total_queries": 10,
            "hits": 3,
            "misses": 7,
            "hit_rate": 30.0
        }
        import asyncio
        res = asyncio.run(cache_stats())
        self.assertIn("Cached queries: 2", res)
        self.assertIn("Total queries: 10", res)
        self.assertIn("Cache hits: 3", res)
        self.assertIn("Cache misses: 7", res)
        self.assertIn("Hit rate: 30.00%", res)

    @patch("src.mcp_server.server.query_cache")
    def test_cache_stats_exception(self, mock_cache):
        mock_cache.stats.side_effect = Exception("Cache error")
        import asyncio
        res = asyncio.run(cache_stats())
        self.assertEqual(res, {"error": "Cache error", "tool": "cache_stats"})

    @patch("src.mcp_server.server.ask")
    def test_ask_database_debug_disabled(self, mock_ask):
        mock_ask.return_value = {
            "answer": "There are 5 employees.",
            "generated_sql": "SELECT COUNT(*) FROM employees",
            "results": [{"count": 5}]
        }
        with patch.dict(os.environ, {"DEBUG_MODE": "False"}):
            import asyncio
            res = asyncio.run(ask_database("How many employees?"))
            self.assertEqual(res, "There are 5 employees.")

    @patch("src.mcp_server.server.ask")
    def test_ask_database_debug_enabled(self, mock_ask):
        mock_ask.return_value = {
            "answer": "There are 5 employees.",
            "generated_sql": "SELECT COUNT(*) FROM employees",
            "results": [{"count": 5}]
        }
        with patch.dict(os.environ, {"DEBUG_MODE": "True"}):
            import asyncio
            res = asyncio.run(ask_database("How many employees?"))
            self.assertIn("There are 5 employees.", res)
            self.assertIn("--- Debug ---", res)
            self.assertIn("SQL: SELECT COUNT(*) FROM employees", res)

    @patch("src.mcp_server.server.ask")
    def test_ask_database_exception(self, mock_ask):
        mock_ask.side_effect = Exception("Ask error")
        import asyncio
        res = asyncio.run(ask_database("How many employees?"))
        self.assertEqual(res, {"error": "Ask error", "tool": "ask_database"})

    @patch("src.mcp_server.server.memory_store")
    @patch("src.mcp_server.server.HRAgent")
    def test_hr_agent_success(self, mock_hr_agent_cls, mock_store):
        mock_session = MagicMock()
        mock_session.get_history.return_value = []
        mock_store.get_or_create.return_value = mock_session

        mock_agent_instance = AsyncMock()
        mock_agent_instance.ask.return_value = {
            "answer": "Final response",
            "steps": 2,
            "tools_used": ["list_tables", "execute_sql"]
        }
        mock_hr_agent_cls.return_value = mock_agent_instance

        import asyncio
        res = asyncio.run(hr_agent("Compare department performance", "session_123"))
        self.assertIn("Final response", res)
        self.assertIn("Used 2 analysis steps: list_tables, execute_sql", res)
        mock_session.add_turn.assert_called_once_with("Compare department performance", "Final response")

    def test_hr_agent_missing_session_id(self):
        import asyncio
        res = asyncio.run(hr_agent("test", ""))
        self.assertEqual(res, "Error: session_id is required and cannot be empty.")

        res = asyncio.run(hr_agent("test", "   "))
        self.assertEqual(res, "Error: session_id is required and cannot be empty.")

    @patch("src.mcp_server.server.memory_store")
    def test_clear_session_success(self, mock_store):
        import asyncio
        res = asyncio.run(clear_session("session_123"))
        self.assertEqual(res, "Session session_123 cleared.")
        mock_store.clear_session.assert_called_once_with("session_123")


if __name__ == "__main__":
    unittest.main()
