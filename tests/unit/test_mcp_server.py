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
    health_groq,
    health_google_sheets,
)


class TestMCPServerTools(unittest.TestCase):
    
    @patch("src.tools.db_tools.metadata_service")
    def test_list_tables_success(self, mock_meta):
        mock_meta.get_tables = AsyncMock(return_value=["employees", "timesheets"])
        import asyncio
        res = asyncio.run(list_tables())
        self.assertEqual(res, ["employees", "timesheets"])

    @patch("src.tools.db_tools.metadata_service")
    def test_list_tables_exception(self, mock_meta):
        mock_meta.get_tables = AsyncMock(side_effect=Exception("DB Error"))
        import asyncio
        res = asyncio.run(list_tables())
        self.assertEqual(res, {"error": "DB Error", "tool": "list_tables"})

    @patch("src.tools.db_tools.metadata_service")
    def test_describe_table_success(self, mock_meta):
        mock_meta.get_table_schema = AsyncMock(return_value={"id": "INTEGER"})
        import asyncio
        res = asyncio.run(describe_table("employees"))
        self.assertEqual(res, {"id": "INTEGER"})

    @patch("src.tools.db_tools.metadata_service")
    def test_describe_table_exception(self, mock_meta):
        mock_meta.get_table_schema = AsyncMock(side_effect=Exception("Schema Error"))
        import asyncio
        res = asyncio.run(describe_table("employees"))
        self.assertEqual(res, {"error": "Schema Error", "tool": "describe_table"})

    @patch("src.tools.db_tools.schema_builder")
    @patch("src.tools.db_tools.sql_validator")
    @patch("src.tools.db_tools.query_service")
    def test_execute_sql_success(self, mock_query, mock_val, mock_sb):
        mock_sb.get_full_schema = AsyncMock(return_value={})
        mock_query.execute_query = AsyncMock(return_value=[{"count": 1}])
        import asyncio
        res = asyncio.run(execute_sql("SELECT count(*) FROM employees"))
        self.assertEqual(res, [{"count": 1}])

    @patch("src.tools.db_tools.schema_builder")
    @patch("src.tools.db_tools.sql_validator")
    def test_execute_sql_validation_error(self, mock_val, mock_sb):
        mock_sb.get_full_schema = AsyncMock(return_value={})
        mock_val.validate.side_effect = Exception("Validation failed")
        import asyncio
        res = asyncio.run(execute_sql("DELETE FROM employees"))
        self.assertEqual(res, {"error": "Validation failed", "tool": "execute_sql"})

    @patch("src.tools.timesheet_tools.timesheet_loader")
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

    @patch("src.tools.hr_tools.hr_handler")
    def test_hr_insights_success(self, mock_hr):
        mock_hr.handle = AsyncMock(return_value="Answer from insights handler")
        import asyncio
        res = asyncio.run(hr_insights("Who is the top performer?"))
        self.assertEqual(res, "Answer from insights handler")

    @patch("src.tools.hr_tools.hr_handler")
    def test_hr_insights_exception(self, mock_hr):
        mock_hr.handle = AsyncMock(side_effect=Exception("Insights error"))
        import asyncio
        res = asyncio.run(hr_insights("Who is the top performer?"))
        self.assertEqual(res, {"error": "Insights error", "tool": "hr_insights"})

    @patch("src.tools.db_tools.query_cache")
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

    @patch("src.tools.db_tools.query_cache")
    def test_cache_stats_exception(self, mock_cache):
        mock_cache.stats.side_effect = Exception("Cache error")
        import asyncio
        res = asyncio.run(cache_stats())
        self.assertEqual(res, {"error": "Cache error", "tool": "cache_stats"})

    @patch("src.tools.db_tools.ask")
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

    @patch("src.tools.db_tools.ask")
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

    @patch("src.tools.db_tools.ask")
    def test_ask_database_exception(self, mock_ask):
        mock_ask.side_effect = Exception("Ask error")
        import asyncio
        res = asyncio.run(ask_database("How many employees?"))
        self.assertEqual(res, {"error": "Ask error", "tool": "ask_database"})

    @patch("src.tools.hr_tools.memory_store")
    @patch("src.agent.hr_agent.HRAgent")
    def test_hr_agent_success(self, mock_hr_agent_cls, mock_store):
        mock_session = MagicMock()
        mock_session.get_history.return_value = []
        mock_store.get_or_create.return_value = mock_session

        mock_agent_instance = AsyncMock()
        mock_agent_instance.ask.return_value = {
            "answer": "Final response",
            "steps": [{"node": "Test Node", "message": "Test Message", "timestamp": "..."}],
            "tools_used": ["list_tables", "execute_sql"],
            "steps_count": 2
        }
        mock_hr_agent_cls.return_value = mock_agent_instance

        import asyncio
        res = asyncio.run(hr_agent("Compare department performance", "session_123"))
        self.assertEqual(res["answer"], "Final response")
        self.assertEqual(len(res["steps"]), 1)
        mock_session.add_turn.assert_called_once_with("Compare department performance", "Final response")

    def test_hr_agent_missing_session_id(self):
        import asyncio
        res = asyncio.run(hr_agent("test", ""))
        self.assertEqual(res, {"error": "session_id is required and cannot be empty.", "success": False})

        res = asyncio.run(hr_agent("test", "   "))
        self.assertEqual(res, {"error": "session_id is required and cannot be empty.", "success": False})

    @patch("src.tools.hr_tools.memory_store")
    def test_clear_session_success(self, mock_store):
        import asyncio
        res = asyncio.run(clear_session("session_123"))
        self.assertEqual(res, "Session session_123 cleared.")
        mock_store.clear_session.assert_called_once_with("session_123")

    @patch("src.services.ai.llm.client")
    def test_health_groq_success(self, mock_client):
        import asyncio
        mock_client.api_key = "fake_key"
        with patch.dict(os.environ, {"GROQ_API_KEY": "fake_key"}):
            res = asyncio.run(health_groq())
            self.assertEqual(res["connected"], True)
            self.assertIn("Groq LLM Service initialized successfully", res["message"])

    def test_health_groq_missing_key(self):
        import asyncio
        with patch.dict(os.environ, {}, clear=True):
            res = asyncio.run(health_groq())
            self.assertEqual(res["connected"], False)
            self.assertIn("GROQ_API_KEY environment variable is not configured", res["message"])

    @patch("src.config.google_config.get_client_secret_path")
    def test_health_google_sheets_missing_secret(self, mock_secret_path_func):
        mock_secret_path = MagicMock()
        mock_secret_path.exists.return_value = False
        mock_secret_path_func.return_value = mock_secret_path
        
        res = health_google_sheets()
        self.assertEqual(res["connected"], False)
        self.assertIn("client_secret.json is missing", res["message"])

    @patch("src.config.google_config.get_client_secret_path")
    @patch("src.config.google_config.get_token_path")
    @patch("google.oauth2.credentials.Credentials")
    @patch("gspread.authorize")
    def test_health_google_sheets_success(self, mock_authorize, mock_creds_cls, mock_token_path_func, mock_secret_path_func):
        mock_secret_path = MagicMock()
        mock_secret_path.exists.return_value = True
        mock_secret_path_func.return_value = mock_secret_path

        mock_token_path = MagicMock()
        mock_token_path.exists.return_value = True
        mock_token_path_func.return_value = mock_token_path

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds

        mock_client = MagicMock()
        mock_authorize.return_value = mock_client

        res = health_google_sheets()
        self.assertEqual(res["connected"], True)
        self.assertIn("authenticated successfully", res["message"])


if __name__ == "__main__":
    unittest.main()
