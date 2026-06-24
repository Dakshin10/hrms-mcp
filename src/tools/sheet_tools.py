from pydantic import BaseModel, Field, model_validator, field_validator, ValidationError
from typing import Optional
from src.core.logging.logger import logger
from src.services.google_sheets_service import (
    connect_google_sheet as _connect_sheet,
    fetch_sheet_data as _fetch_sheet,
    import_sheet_data as _import_sheet
)

class FetchSheetDataArguments(BaseModel):
    spreadsheet_id: Optional[str] = Field(None, description="The 44-character Google Spreadsheet ID")
    sheet_url: Optional[str] = Field(None, description="The full Google Sheets URL")
    worksheet_name: Optional[str] = Field(None, description="The worksheet name (e.g. 'Sheet1')")
    max_rows: Optional[int] = Field(50, description="The maximum number of rows to retrieve")

    @model_validator(mode="after")
    def validate_id_or_url(self) -> 'FetchSheetDataArguments':
        if not self.spreadsheet_id and not self.sheet_url:
            raise ValueError("Either spreadsheet_id or sheet_url must be provided.")
        return self

    @field_validator("max_rows")
    @classmethod
    def validate_max_rows(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("max_rows must be greater than 0.")
        return v


class ConnectGoogleSheetArguments(BaseModel):
    sheet_url: str = Field(..., min_length=1, description="The full Google Sheets URL to connect and import")


async def connect_google_sheet(sheet_url: str) -> dict:
    """
    Connect to a Google Sheet via URL, validate access, read worksheet data,
    infer column types, recreate database table in D1, import rows,
    record sync metadata, and invalidate caches.
    """
    logger.info(f"MCP Tool connect_google_sheet invoked for sheet_url: {sheet_url}")
    
    try:
        args = ConnectGoogleSheetArguments(sheet_url=sheet_url)
    except ValidationError as ve:
        error_msg = f"Argument validation failed: {ve}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
        
    try:
        result = await _connect_sheet(args.sheet_url)
        return result
    except Exception as e:
        error_msg = f"Unexpected error during connect_google_sheet execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg
        }


def fetch_sheet_data(
    spreadsheet_id: Optional[str] = None,
    sheet_url: Optional[str] = None,
    worksheet_name: Optional[str] = None,
    max_rows: int = 50,
) -> dict:
    """
    Fetch live rows from a connected Google Sheet. Returns worksheet name, row count, and data as a list of dicts.
    Either spreadsheet_id or sheet_url must be provided.
    """
    logger.info(
        f"MCP Tool fetch_sheet_data invoked: spreadsheet_id='{spreadsheet_id}', "
        f"sheet_url='{sheet_url}', worksheet_name='{worksheet_name}', max_rows={max_rows}"
    )
    
    try:
        # 1. Pydantic validation
        args = FetchSheetDataArguments(
            spreadsheet_id=spreadsheet_id,
            sheet_url=sheet_url,
            worksheet_name=worksheet_name,
            max_rows=max_rows
        )
    except ValidationError as ve:
        errors = ve.errors()
        error_messages = []
        for err in errors:
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            error_messages.append(f"{loc}: {msg}" if loc else msg)
        
        error_msg = "Argument validation failed: " + "; ".join(error_messages)
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }

    # 2. Execution and exception handling
    try:
        result = _fetch_sheet(
            spreadsheet_id=args.spreadsheet_id,
            sheet_url=args.sheet_url,
            worksheet_name=args.worksheet_name,
            max_rows=args.max_rows
        )
        
        if "error" in result:
            logger.error(f"Error in Sheets service fetch: {result['error']}")
            return {
                "success": False,
                "error": result["error"]
            }
            
        logger.info(f"Successfully retrieved sheet data: {result.get('row_count')} rows fetched.")
        return {
            "success": True,
            "worksheet": result.get("worksheet"),
            "row_count": result.get("row_count"),
            "data": result.get("data")
        }
    except Exception as e:
        error_msg = f"Unexpected error while fetching sheet data: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg
        }


def health_google_sheets() -> dict:
    """
    Check the health and connection status of the Google Sheets API integration.
    Validates OAuth credentials, tokens, and OAuth refresh.
    Does NOT block on run_local_server if credentials are missing/invalid.
    """
    logger.info("MCP Tool health_google_sheets invoked")
    try:
        from src.config.google_config import get_client_secret_path, get_token_path
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import gspread
        
        token_path = get_token_path()
        secret_path = get_client_secret_path()
        
        # 1. Check if client_secret.json exists
        if not secret_path.exists():
            return {
                "connected": False,
                "message": f"Required client_secret.json is missing at {secret_path}"
            }
            
        # 2. Check if token.json exists
        if not token_path.exists():
            return {
                "connected": False,
                "message": f"Authorization token.json is missing at {token_path}. Run connect_google_sheet to login."
            }
            
        # 3. Load credentials and try refreshing silently
        creds = Credentials.from_authorized_user_file(str(token_path))
        
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.info("[Health Check] Refreshing expired Google credentials silently")
                creds.refresh(Request())
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            else:
                return {
                    "connected": False,
                    "message": "Google credentials are invalid or expired, and cannot be refreshed."
                }
                
        # 4. Authorize gspread client
        client = gspread.authorize(creds)
        if client:
            return {
                "connected": True,
                "message": "Google Sheets API authenticated successfully"
            }
        return {
            "connected": False,
            "message": "Failed to authorize gspread client"
        }
    except Exception as e:
        logger.error(f"Google Sheets health check failed: {e}")
        return {
            "connected": False,
            "message": str(e)
        }


class ImportSheetDataArguments(BaseModel):
    spreadsheet_id: Optional[str] = Field(None, description="The 44-character Google Spreadsheet ID")
    worksheet_title: Optional[str] = Field(None, description="The title of the worksheet (e.g. 'Sheet1')")
    table_name: Optional[str] = Field(None, description="The name of the D1 table to create/overwrite")
    overwrite: bool = Field(True, description="Whether to drop the table if it already exists")
    sheet_url: Optional[str] = Field(None, description="The full Google Sheets URL (backward compatibility fallback)")
    worksheet_name: Optional[str] = Field(None, description="The worksheet name (backward compatibility fallback)")
    max_rows: Optional[int] = Field(None, description="The maximum number of rows to import (None imports all)")

    @model_validator(mode="after")
    def validate_id_or_url(self) -> 'ImportSheetDataArguments':
        if not self.spreadsheet_id and not self.sheet_url:
            raise ValueError("Either spreadsheet_id or sheet_url must be provided.")
        return self


async def import_sheet_data(
    spreadsheet_id: str = None,
    worksheet_title: str = None,
    table_name: str = None,
    overwrite: bool = True,
    sheet_url: str = None,
    worksheet_name: str = None,
    max_rows: int = None,
) -> dict:
    """
    Import live rows from a Google Sheet into Cloudflare D1. Automatically infers types,
    creates/overwrites tables, filters empty/duplicate rows, inserts records, and invalidates caches.
    """
    logger.info(
        f"MCP Tool import_sheet_data invoked: spreadsheet_id='{spreadsheet_id}', "
        f"worksheet_title='{worksheet_title}', table_name='{table_name}', overwrite={overwrite}"
    )

    try:
        # 1. Validation
        args = ImportSheetDataArguments(
            spreadsheet_id=spreadsheet_id,
            worksheet_title=worksheet_title,
            table_name=table_name,
            overwrite=overwrite,
            sheet_url=sheet_url,
            worksheet_name=worksheet_name,
            max_rows=max_rows
        )
    except ValidationError as ve:
        error_msg = f"Argument validation failed: {ve}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }

    # 2. Ingestion
    try:
        result = await _import_sheet(
            spreadsheet_id=args.spreadsheet_id,
            worksheet_title=args.worksheet_title,
            table_name=args.table_name,
            overwrite=args.overwrite,
            sheet_url=args.sheet_url,
            worksheet_name=args.worksheet_name,
            max_rows=args.max_rows
        )
        return result
    except Exception as e:
        error_msg = f"Unexpected error during import execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg
        }
