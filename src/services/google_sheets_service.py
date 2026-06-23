import logging
import re
from datetime import datetime
from src.services.google_auth import get_gspread_client

logger = logging.getLogger(__name__)

# Module-level in-memory registry for connected spreadsheets
_sheet_registry: dict[str, dict] = {}

def _extract_spreadsheet_id(url_or_id: str) -> str:
    """
    Extracts the spreadsheet ID from a raw ID or a Google Sheets URL.
    Returns the 44-character spreadsheet ID.
    Raises ValueError if invalid.
    """
    # Check for exact match of 44-character spreadsheet ID
    if re.match(r"^[a-zA-Z0-9_-]{44}$", url_or_id):
        return url_or_id

    # Check for spreadsheet ID inside a Google Sheets URL
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        extracted_id = match.group(1)
        # Ensure the extracted ID is valid (typically 44 chars)
        if len(extracted_id) >= 40:
            return extracted_id

    raise ValueError(
        f"Invalid spreadsheet URL or ID provided: '{url_or_id}'. "
        f"Must be a 44-character Google Sheet ID or a valid spreadsheet URL."
    )

def connect_google_sheet(url: str) -> dict:
    """Connect to a live Google Sheet by URL. Authenticates via OAuth2, validates access, and registers the sheet. Returns spreadsheet title and available worksheets."""
    try:
        logger.info(f"Connecting to Google Sheet via URL: {url}")
        spreadsheet_id = _extract_spreadsheet_id(url)
        
        client = get_gspread_client()
        logger.info(f"Opening spreadsheet with ID: {spreadsheet_id}")
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        worksheets = []
        for ws in spreadsheet.worksheets():
            worksheets.append({
                "title": ws.title,
                "id": ws.id,
                "row_count": ws.row_count,
                "col_count": ws.col_count
            })
            
        _sheet_registry[spreadsheet_id] = {
            "spreadsheet_id": spreadsheet_id,
            "title": spreadsheet.title,
            "url": url,
            "worksheets": worksheets,
            "last_fetched_at": None
        }
        
        logger.info(f"Successfully connected to spreadsheet: '{spreadsheet.title}'")
        return {
            "status": "connected",
            "spreadsheet_id": spreadsheet_id,
            "title": spreadsheet.title,
            "url": url,
            "worksheet_count": len(worksheets),
            "worksheets": worksheets,
            "message": f"Connected to '{spreadsheet.title}' — {len(worksheets)} worksheet(s) available."
        }
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheet: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }

def fetch_sheet_data(spreadsheet_id: str, worksheet_title: str = None, max_rows: int = 500) -> dict:
    """Fetch live rows from a connected Google Sheet. Returns rows as a list of dicts keyed by column headers. Defaults to the first worksheet if no title is given."""
    try:
        logger.info(f"Fetching data for spreadsheet ID: {spreadsheet_id}, worksheet: {worksheet_title}")
        client = get_gspread_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        if worksheet_title:
            logger.info(f"Accessing worksheet by title: {worksheet_title}")
            ws = spreadsheet.worksheet(worksheet_title)
        else:
            logger.info("No worksheet title provided, defaulting to the first worksheet")
            ws = spreadsheet.sheet1
            
        logger.info("Reading records from worksheet")
        full_records = ws.get_all_records()
        
        records = full_records[:max_rows]
        truncated = len(full_records) > max_rows
        
        if spreadsheet_id in _sheet_registry:
            _sheet_registry[spreadsheet_id]["last_fetched_at"] = datetime.utcnow().isoformat()
            
        logger.info(f"Successfully fetched {len(records)} rows from worksheet '{ws.title}'")
        return {
            "status": "success",
            "spreadsheet_id": spreadsheet_id,
            "worksheet": ws.title,
            "total_rows": len(full_records),
            "returned_rows": len(records),
            "columns": list(records[0].keys()) if records else [],
            "data": records,
            "truncated": truncated
        }
    except Exception as e:
        logger.error(f"Failed to fetch Google Sheet data: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }
