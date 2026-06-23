import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import os
import gspread

from src.services.google_auth import get_gspread_client
from src.services.google_sheets_service import (
    _extract_spreadsheet_id,
    connect_google_sheet,
    fetch_sheet_data,
    _sheet_registry
)

class TestGoogleSheetsAuthAndService(unittest.TestCase):

    def setUp(self):
        _sheet_registry.clear()

    def test_extract_spreadsheet_id_valid_id(self):
        # A valid spreadsheet ID has 44 characters
        valid_id = "1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcde"
        # Wait, let's make sure it is exactly 44 characters
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

    @patch("src.services.google_auth.Credentials")
    @patch("src.services.google_auth.gspread.authorize")
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

    @patch("src.services.google_auth.Credentials")
    @patch("src.services.google_auth.Request")
    @patch("src.services.google_auth.gspread.authorize")
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
    def test_connect_google_sheet_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.title = "Test Sheet"
        
        mock_ws = MagicMock()
        mock_ws.title = "Sheet1"
        mock_ws.id = 123
        mock_ws.row_count = 100
        mock_ws.col_count = 10
        mock_spreadsheet.worksheets.return_value = [mock_ws]
        
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        url = "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit"
        res = connect_google_sheet(url)

        self.assertEqual(res["status"], "connected")
        self.assertEqual(res["title"], "Test Sheet")
        self.assertEqual(res["worksheet_count"], 1)
        self.assertEqual(res["worksheets"][0]["title"], "Sheet1")
        self.assertIn("1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg", _sheet_registry)

    @patch("src.services.google_sheets_service.get_gspread_client")
    def test_connect_google_sheet_error(self, mock_get_client):
        mock_get_client.side_effect = Exception("API Connection failure")
        url = "https://docs.google.com/spreadsheets/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg/edit"
        res = connect_google_sheet(url)
        self.assertEqual(res["status"], "error")
        self.assertIn("API Connection failure", res["message"])

    @patch("src.services.google_sheets_service.get_gspread_client")
    def test_fetch_sheet_data_default_worksheet_slice(self, mock_get_client):
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_ws = MagicMock()
        mock_ws.title = "Sheet1"
        
        # 3 mock records
        mock_records = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"}
        ]
        mock_ws.get_all_records.return_value = mock_records
        mock_spreadsheet.sheet1 = mock_ws
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        # Seed registry
        sheet_id = "1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg"
        _sheet_registry[sheet_id] = {"last_fetched_at": None}

        # Fetch with max_rows = 2
        res = fetch_sheet_data(sheet_id, max_rows=2)

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["worksheet"], "Sheet1")
        self.assertEqual(res["total_rows"], 3)
        self.assertEqual(res["returned_rows"], 2)
        self.assertEqual(res["truncated"], True)
        self.assertEqual(res["data"], [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
        self.assertIsNotNone(_sheet_registry[sheet_id]["last_fetched_at"])

    @patch("src.services.google_sheets_service.get_gspread_client")
    def test_fetch_sheet_data_specific_worksheet_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_ws = MagicMock()
        mock_ws.title = "Analytics"
        mock_ws.get_all_records.return_value = [{"kpi": 95}]
        
        mock_spreadsheet.worksheet.return_value = mock_ws
        mock_client.open_by_key.return_value = mock_spreadsheet
        mock_get_client.return_value = mock_client

        sheet_id = "1aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789_abcdefg"
        res = fetch_sheet_data(sheet_id, worksheet_title="Analytics")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["worksheet"], "Analytics")
        self.assertEqual(res["total_rows"], 1)
        self.assertEqual(res["returned_rows"], 1)
        self.assertEqual(res["truncated"], False)
        self.assertEqual(res["columns"], ["kpi"])
        mock_spreadsheet.worksheet.assert_called_once_with("Analytics")

    @patch("src.services.google_sheets_service.get_gspread_client")
    def test_fetch_sheet_data_error_handled(self, mock_get_client):
        mock_get_client.side_effect = Exception("Worksheet not found")
        res = fetch_sheet_data("some_sheet_id")
        self.assertEqual(res["status"], "error")
        self.assertIn("Worksheet not found", res["message"])

if __name__ == "__main__":
    unittest.main()
