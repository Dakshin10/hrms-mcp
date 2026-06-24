import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import gspread

from src.services.google_sheets_service import (
    get_gspread_client,
    _extract_spreadsheet_id,
    connect_google_sheet,
    fetch_sheet_data,
    _sheet_registry
)

class TestGoogleSheetsAuthAndService(unittest.TestCase):

    def setUp(self):
        _sheet_registry.clear()

    def test_extract_spreadsheet_id_valid_id(self):
        valid_id = "1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdef"
        self.assertEqual(len(valid_id), 44)
        result = _extract_spreadsheet_id(valid_id)
        self.assertEqual(result, valid_id)

    def test_extract_spreadsheet_id_valid_url(self):
        url = "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit#gid=0"
        result = _extract_spreadsheet_id(url)
        self.assertEqual(result, "1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg")

    def test_extract_spreadsheet_id_invalid(self):
        with self.assertRaises(ValueError):
            _extract_spreadsheet_id("short_id")
        with self.assertRaises(ValueError):
            _extract_spreadsheet_id("https://google.com")

    def test_google_auth_missing_secrets_raises_error(self):
        original_exists = Path.exists
        try:
            # Setup mock so token.json doesn't exist and client_secret.json doesn't exist
            Path.exists = lambda self_path: False

            with self.assertRaises(FileNotFoundError):
                get_gspread_client()
        finally:
            Path.exists = original_exists

    @patch("src.services.google_sheets_service.Credentials")
    @patch("src.services.google_sheets_service.gspread.authorize")
    def test_google_auth_valid_token_success(self, mock_authorize, mock_creds_cls):
        original_exists = Path.exists
        try:
            # Setup path exists to return True only for token.json
            Path.exists = lambda self_path: "token.json" in str(self_path)

            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds_cls.from_authorized_user_file.return_value = mock_creds

            mock_client = MagicMock()
            mock_authorize.return_value = mock_client

            client = get_gspread_client()
            self.assertEqual(client, mock_client)
            mock_creds_cls.from_authorized_user_file.assert_called_once()
            mock_authorize.assert_called_once_with(mock_creds)
        finally:
            Path.exists = original_exists

    @patch("src.services.google_sheets_service.Credentials")
    @patch("src.services.google_sheets_service.Request")
    @patch("src.services.google_sheets_service.gspread.authorize")
    @patch("builtins.open", new_callable=mock_open)
    def test_google_auth_expired_token_silent_refresh(self, mock_file, mock_authorize, mock_request, mock_creds_cls):
        original_exists = Path.exists
        try:
            # Token and everything exists
            Path.exists = lambda self_path: True

            mock_creds = MagicMock()
            mock_creds.valid = False
            mock_creds.expired = True
            mock_creds.refresh_token = "some_refresh_token"
            mock_creds.to_json.return_value = '{"refreshed": true}'
            
            # When refresh is called, it should make the token valid
            def refresh_side_effect(*args, **kwargs):
                mock_creds.valid = True
            mock_creds.refresh.side_effect = refresh_side_effect
            
            mock_creds_cls.from_authorized_user_file.return_value = mock_creds

            mock_client = MagicMock()
            mock_authorize.return_value = mock_client

            client = get_gspread_client()
            self.assertEqual(client, mock_client)
            mock_creds.refresh.assert_called_once()
            mock_file.assert_called_once()
        finally:
            Path.exists = original_exists



    @patch("src.services.google_sheets_service.get_gspread_client")
    def test_fetch_sheet_data_default_worksheet_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_ws = MagicMock()
        mock_ws.title = "Employees"
        
        mock_records = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
        mock_ws.get_all_records.return_value = mock_records
        mock_spreadsheet.sheet1 = mock_ws
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        # Seed registry
        sheet_id = "1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg"
        _sheet_registry[sheet_id] = {"last_fetched_at": None}

        res = fetch_sheet_data(sheet_id)

        self.assertEqual(res["worksheet"], "Employees")
        self.assertEqual(res["row_count"], 2)
        self.assertEqual(res["data"], mock_records)
        self.assertIsNotNone(_sheet_registry[sheet_id]["last_fetched_at"])

    @patch("src.services.google_sheets_service.get_gspread_client")
    def test_fetch_sheet_data_specific_worksheet_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_ws = MagicMock()
        mock_ws.title = "Timesheets"
        mock_records = [{"employee_id": "EMP0001", "task": "Testing"}]
        mock_ws.get_all_records.return_value = mock_records
        
        mock_spreadsheet.worksheet.return_value = mock_ws
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        sheet_id = "1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg"
        res = fetch_sheet_data(sheet_id, worksheet_name="Timesheets")

        self.assertEqual(res["worksheet"], "Timesheets")
        self.assertEqual(res["row_count"], 1)
        self.assertEqual(res["data"], mock_records)
        mock_spreadsheet.worksheet.assert_called_once_with("Timesheets")

    @patch("src.services.google_sheets_service.get_gspread_client")
    def test_fetch_sheet_data_error_handled(self, mock_get_client):
        mock_get_client.side_effect = Exception("Worksheet not found")
        res = fetch_sheet_data("1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdef")
        self.assertIn("error", res)
        self.assertIn("Worksheet not found", res["error"])


from src.tools.sheet_tools import fetch_sheet_data as mcp_fetch_sheet_data

class TestGoogleSheetsMCPTool(unittest.TestCase):

    def setUp(self):
        _sheet_registry.clear()

    @patch("src.tools.sheet_tools._fetch_sheet")
    def test_mcp_fetch_sheet_data_validation_success(self, mock_fetch):
        mock_fetch.return_value = {
            "worksheet": "Sheet1",
            "row_count": 2,
            "data": [{"id": "1"}, {"id": "2"}]
        }
        res = mcp_fetch_sheet_data(
            spreadsheet_id="1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg",
            worksheet_name="Sheet1",
            max_rows=10
        )
        self.assertEqual(res["success"], True)
        self.assertEqual(res["worksheet"], "Sheet1")
        self.assertEqual(res["row_count"], 2)
        mock_fetch.assert_called_once_with(
            spreadsheet_id="1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg",
            sheet_url=None,
            worksheet_name="Sheet1",
            max_rows=10
        )

    def test_mcp_fetch_sheet_data_validation_error_missing_identifiers(self):
        res = mcp_fetch_sheet_data(worksheet_name="Sheet1")
        self.assertEqual(res["success"], False)
        self.assertIn("validation failed", res["error"].lower())

    def test_mcp_fetch_sheet_data_validation_error_invalid_max_rows(self):
        res = mcp_fetch_sheet_data(
            spreadsheet_id="1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg",
            max_rows=0
        )
        self.assertEqual(res["success"], False)
        self.assertIn("validation failed", res["error"].lower())

    @patch("src.tools.sheet_tools._fetch_sheet")
    def test_mcp_fetch_sheet_data_backward_compatibility(self, mock_fetch):
        mock_fetch.return_value = {
            "worksheet": "Timesheets",
            "row_count": 1,
            "data": [{"id": "1"}]
        }
        res = mcp_fetch_sheet_data(
            sheet_url="https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit",
            worksheet_name="Timesheets"
        )
        self.assertEqual(res["success"], True)
        self.assertEqual(res["worksheet"], "Timesheets")
        mock_fetch.assert_called_once_with(
            spreadsheet_id=None,
            sheet_url="https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit",
            worksheet_name="Timesheets",
            max_rows=50
        )

    @patch("src.tools.sheet_tools._fetch_sheet")
    def test_mcp_fetch_sheet_data_service_error_handled(self, mock_fetch):
        mock_fetch.return_value = {"error": "API Failure"}
        res = mcp_fetch_sheet_data(
            spreadsheet_id="1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg"
        )
        self.assertEqual(res["success"], False)
        self.assertEqual(res["error"], "API Failure")


from src.services.google_sheets_service import (
    normalize_column_name,
    normalize_table_name,
    infer_column_type,
    import_sheet_data as service_import_sheet_data
)
from src.tools.sheet_tools import import_sheet_data as mcp_import_sheet_data

class TestGoogleSheetsIngestionHelpers(unittest.TestCase):

    def test_normalize_column_name(self):
        self.assertEqual(normalize_column_name("Employee ID", 0), "employee_id")
        self.assertEqual(normalize_column_name("1st Name", 1), "col_1st_name")
        self.assertEqual(normalize_column_name("Salary (INR)!!!", 2), "salary_inr")
        self.assertEqual(normalize_column_name("   ", 3), "col_3")
        self.assertEqual(normalize_column_name("Duplicate_Col", 4), "duplicate_col")

    def test_normalize_table_name(self):
        self.assertEqual(normalize_table_name("Active Projects"), "active_projects")
        self.assertEqual(normalize_table_name("2026 Budget"), "tbl_2026_budget")
        self.assertEqual(normalize_table_name("   "), "imported_table")

    def test_infer_column_type(self):
        self.assertEqual(infer_column_type(["1", "2", "3"]), "INTEGER")
        self.assertEqual(infer_column_type(["1.5", "2", "3.0"]), "REAL")
        self.assertEqual(infer_column_type(["2026-06-24", "2026-06-25"]), "DATE")
        self.assertEqual(infer_column_type(["2026-06-24", "text"]), "TEXT")
        self.assertEqual(infer_column_type(["", "   ", None]), "TEXT")


class TestGoogleSheetsIngestionPipeline(unittest.IsolatedAsyncioTestCase):

    @patch("src.services.google_sheets_service.fetch_sheet_data")
    @patch("src.services.google_sheets_service.D1Client")
    @patch("src.services.google_sheets_service.metadata_service.clear_cache")
    @patch("src.services.google_sheets_service.schema_builder.invalidate")
    async def test_import_sheet_data_success(self, mock_invalidate, mock_clear_cache, mock_d1_cls, mock_fetch):
        # Setup mocks
        mock_fetch.return_value = {
            "worksheet": "Projects",
            "row_count": 3,
            "data": [
                {"Project ID": "1", "Project Name": "Alpha", "Start Date": "2026-01-01", "Budget": "100000.50"},
                {"Project ID": "2", "Project Name": "Beta", "Start Date": "2026-02-01", "Budget": "200000.00"},
                {"Project ID": "2", "Project Name": "Beta", "Start Date": "2026-02-01", "Budget": "200000.00"} # Duplicate row
            ]
        }

        mock_d1 = MagicMock()
        
        async def mock_execute(sql, params=None):
            if "sqlite_master" in sql:
                return {"results": [{"name": "projects"}]}
            elif "COUNT(*)" in sql:
                return {"results": [{"cnt": 2}]}
            return {"results": []}

        mock_d1.execute = mock_execute
        mock_d1_cls.return_value = mock_d1

        # Run pipeline
        res = await service_import_sheet_data(
            spreadsheet_id="1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg",
            worksheet_title="Projects",
            overwrite=True
        )

        self.assertEqual(res["success"], True)
        self.assertEqual(res["table_name"], "projects")
        self.assertEqual(res["rows_imported"], 2)
        self.assertEqual(res["columns"], 4)
        mock_clear_cache.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("src.tools.sheet_tools._import_sheet")
    def test_mcp_import_sheet_data_validation_errors(self, mock_import):
        import asyncio
        # Missing identifier (spreadsheet_id or sheet_url)
        res = asyncio.run(mcp_import_sheet_data(worksheet_title="Projects"))
        self.assertEqual(res["success"], False)
        self.assertIn("validation failed", res["error"].lower())
        mock_import.assert_not_called()


from src.tools.sheet_tools import connect_google_sheet as mcp_connect_google_sheet

class TestGoogleSheetsConnectIngestionPipeline(unittest.IsolatedAsyncioTestCase):

    @patch("src.services.google_sheets_service.get_gspread_client")
    @patch("src.services.google_sheets_service.D1Client")
    @patch("src.services.google_sheets_service.metadata_service.clear_cache")
    @patch("src.services.google_sheets_service.schema_builder.invalidate")
    async def test_connect_google_sheet_first_import(self, mock_invalidate, mock_clear_cache, mock_d1_cls, mock_get_client):
        # Mocks for gspread
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.title = "Employee Projects"
        mock_ws = MagicMock()
        mock_ws.title = "Sheet1"
        
        mock_records = [
            {"Emp ID": "1", "Emp Name": "Alice", "Worked Hours": "40"},
            {"Emp ID": "2", "Emp Name": "Bob", "Worked Hours": "35"}
        ]
        mock_ws.get_all_records.return_value = mock_records
        mock_spreadsheet.worksheets.return_value = [mock_ws]
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        # Mocks for D1
        mock_d1 = MagicMock()
        async def mock_execute(sql, params=None):
            if "SELECT table_name" in sql:
                return {"results": []}
            elif "sqlite_master" in sql:
                return {"results": [{"name": "employee_projects"}]}
            elif "COUNT(*)" in sql:
                return {"results": [{"cnt": 2}]}
            return {"results": []}
            
        mock_d1.execute = mock_execute
        mock_d1_cls.return_value = mock_d1

        # Run pipeline
        url = "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit"
        res = await connect_google_sheet(url)

        self.assertEqual(res["success"], True)
        self.assertEqual(res["spreadsheet_title"], "Employee Projects")
        self.assertEqual(res["table_name"], "employee_projects")
        self.assertEqual(res["rows_imported"], 2)
        self.assertEqual(res["action"], "created")
        mock_clear_cache.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("src.services.google_sheets_service.get_gspread_client")
    @patch("src.services.google_sheets_service.D1Client")
    @patch("src.services.google_sheets_service.metadata_service.clear_cache")
    @patch("src.services.google_sheets_service.schema_builder.invalidate")
    async def test_connect_google_sheet_reimport_sync(self, mock_invalidate, mock_clear_cache, mock_d1_cls, mock_get_client):
        # Mocks for gspread
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.title = "Employee Projects"
        mock_ws = MagicMock()
        mock_ws.title = "Sheet1"
        
        mock_records = [
            {"Emp ID": "1", "Emp Name": "Alice", "Worked Hours": "45"}
        ]
        mock_ws.get_all_records.return_value = mock_records
        mock_spreadsheet.worksheets.return_value = [mock_ws]
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        # Mocks for D1
        mock_d1 = MagicMock()
        async def mock_execute(sql, params=None):
            if "SELECT table_name" in sql:
                return {"results": [{"table_name": "custom_projects_table"}]}
            elif "sqlite_master" in sql:
                return {"results": [{"name": "custom_projects_table"}]}
            elif "COUNT(*)" in sql:
                return {"results": [{"cnt": 1}]}
            return {"results": []}
            
        mock_d1.execute = mock_execute
        mock_d1_cls.return_value = mock_d1

        # Run pipeline
        url = "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit"
        res = await connect_google_sheet(url)

        self.assertEqual(res["success"], True)
        self.assertEqual(res["spreadsheet_title"], "Employee Projects")
        self.assertEqual(res["table_name"], "custom_projects_table")
        self.assertEqual(res["rows_imported"], 1)
        self.assertEqual(res["action"], "updated")
        mock_clear_cache.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("src.services.google_sheets_service.get_gspread_client")
    async def test_connect_google_sheet_error(self, mock_get_client):
        mock_get_client.side_effect = Exception("API Connection failure")
        url = "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit"
        res = await connect_google_sheet(url)
        self.assertEqual(res["success"], False)
        self.assertIn("API Connection failure", res["error"])

    @patch("src.tools.sheet_tools._connect_sheet")
    def test_mcp_connect_google_sheet_validation_errors(self, mock_connect):
        import asyncio
        res = asyncio.run(mcp_connect_google_sheet(sheet_url=""))
        self.assertEqual(res["success"], False)
        self.assertIn("validation failed", res["error"].lower())
        mock_connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
