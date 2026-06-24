import logging
import re
from datetime import datetime
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.config.google_config import get_client_secret_path, get_token_path
from src.services.database.d1_client import D1Client
from src.services.database.metadata_service import metadata_service
from src.services.ai import schema_builder

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

# Module-level in-memory registry for connected spreadsheets
_sheet_registry: dict[str, dict] = {}

def get_gspread_client() -> gspread.Client:
    """
    Authenticates against Google APIs using local token.json or client_secret.json,
    maintains token lifecycle, and returns an authorized gspread.Client instance.
    """
    token_path = get_token_path()
    secret_path = get_client_secret_path()

    creds = None

    # 1. Load token.json if it exists
    if token_path.exists():
        try:
            logger.info(f"Loading Google credentials from token file: {token_path}")
            creds = Credentials.from_authorized_user_file(str(token_path))
        except Exception as e:
            logger.warning(f"Failed to load credentials from token.json: {e}")
            creds = None

    # 2. Handle invalid/expired credentials
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired Google credentials silently")
                creds.refresh(Request())
                token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                logger.warning(f"Silently refreshing token failed: {e}. Falling back to flow.")
                creds = None

    # 3. If still no valid credentials, run the local server flow
    if not creds or not creds.valid:
        if not secret_path.exists():
            raise FileNotFoundError(
                f"Required client_secret.json file is missing from the credentials directory at: {secret_path}. "
                "Please place your Google OAuth Client Secrets JSON file in the credentials directory."
            )

        logger.info("Starting local OAuth2 authorization flow")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
            # Overwrite/save new token
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
        except Exception as e:
            logger.error(f"Failed to execute OAuth2 flow: {e}")
            raise

    # 4. Authorize gspread client
    logger.info("Authorizing gspread client with credentials")
    client = gspread.authorize(creds)
    return client


def _extract_spreadsheet_id(url_or_id: str) -> str:
    """
    Extracts the spreadsheet ID from a raw ID or a Google Sheets URL.
    Returns the 44-character spreadsheet ID.
    Raises ValueError if invalid.
    """
    if not url_or_id:
        raise ValueError("Spreadsheet URL or ID cannot be empty.")

    # Check for match of 40-50 character spreadsheet ID
    if re.match(r"^[a-zA-Z0-9_-]{40,50}$", url_or_id):
        return url_or_id

    # Check for spreadsheet ID inside a Google Sheets URL
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        extracted_id = match.group(1)
        if len(extracted_id) >= 40:
            return extracted_id

    raise ValueError(
        f"Invalid spreadsheet URL or ID provided: '{url_or_id}'. "
        f"Must be a 40-50 character Google Sheet ID or a valid spreadsheet URL."
    )


async def connect_google_sheet(sheet_url: str) -> dict:
    """
    Connect to a Google Sheet via URL, validate access, read first worksheet,
    infer column types, recreate database table in D1, import rows,
    record sync metadata in `imported_datasets`, and invalidate caches.
    """
    import time
    from datetime import datetime, timezone
    
    start_time = time.perf_counter()
    logger.info(f"Starting Google Sheet connect & ingestion workflow for URL: {sheet_url}")
    
    try:
        # 1. Extract spreadsheet_id from URL
        spreadsheet_id = _extract_spreadsheet_id(sheet_url)
        logger.info(f"Extracted spreadsheet ID: {spreadsheet_id}")
        
        # 2. Authenticate and open spreadsheet
        client = get_gspread_client()
        logger.info(f"Opening spreadsheet: {spreadsheet_id}")
        spreadsheet = client.open_by_key(spreadsheet_id)
        spreadsheet_title = spreadsheet.title
        
        # Get the first worksheet
        worksheets = spreadsheet.worksheets()
        if not worksheets:
            raise ValueError("Spreadsheet has no worksheets.")
        ws = worksheets[0]
        worksheet_name = ws.title
        logger.info(f"Connected to spreadsheet '{spreadsheet_title}'. Selected first worksheet: '{worksheet_name}'")
        
        # 3. Read worksheet records
        logger.info("Reading records from worksheet...")
        records = ws.get_all_records()
        rows_read = len(records)
        logger.info(f"Read {rows_read} rows from worksheet.")
        
        if not records:
            raise ValueError("No records found in the worksheet. Cannot import an empty sheet.")
            
        # Get headers
        headers = list(records[0].keys())
        if not headers:
            raise ValueError("No columns/headers found in the worksheet.")
            
        d1_client = D1Client()
        
        # 4. Ensure imported_datasets table exists in D1
        create_meta_table_sql = """
        CREATE TABLE IF NOT EXISTS imported_datasets (
            spreadsheet_id TEXT PRIMARY KEY,
            spreadsheet_title TEXT,
            worksheet_name TEXT,
            table_name TEXT,
            row_count INTEGER,
            last_synced_at TEXT
        );
        """
        logger.info("Ensuring imported_datasets metadata table exists in D1...")
        await d1_client.execute(create_meta_table_sql)
        
        # 5. Check if spreadsheet_id already exists in metadata
        check_meta_sql = "SELECT table_name FROM imported_datasets WHERE spreadsheet_id = ?"
        meta_res = await d1_client.execute(check_meta_sql, [spreadsheet_id])
        
        existing_table_name = None
        action = "created"
        
        if meta_res and meta_res.get("results"):
            existing_table_name = meta_res["results"][0].get("table_name")
            action = "updated"
            logger.info(f"Found existing import for spreadsheet_id '{spreadsheet_id}' in table '{existing_table_name}'. Sync action set to 'updated'.")
            
        # 6. Determine target table name
        if existing_table_name:
            table_name = existing_table_name
        else:
            table_name = normalize_table_name(spreadsheet_title)
            
        logger.info(f"Normalized D1 table name: '{table_name}'")
        
        # 7. Normalize column names and infer types
        normalized_cols = []
        seen_cols = set()
        for idx, col in enumerate(headers):
            norm = normalize_column_name(col, idx)
            original_norm = norm
            counter = 1
            while norm in seen_cols:
                norm = f"{original_norm}_{counter}"
                counter += 1
            seen_cols.add(norm)
            normalized_cols.append(norm)

        # Infer types for each column
        inferred_types = []
        for col in headers:
            col_values = [r.get(col) for r in records]
            inferred_types.append(infer_column_type(col_values))

        # 8. Build D1 table schema definition
        col_defs = []
        for col_name, col_type in zip(normalized_cols, inferred_types):
            col_defs.append(f"{col_name} {col_type}")

        create_table_sql = f"CREATE TABLE {table_name} ({', '.join(col_defs)});"

        # 9. Recreate the table (drop then create)
        logger.info(f"Recreating D1 table. Dropping existing table if exists: '{table_name}'")
        await d1_client.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        logger.info(f"Creating D1 table with SQL: {create_table_sql}")
        await d1_client.execute(create_table_sql)

        # 10. Filter empty rows and deduplicate records
        unique_records = []
        seen_rows = set()
        skipped_empty = 0
        skipped_dup = 0

        for r in records:
            is_empty = all(val is None or str(val).strip() == "" for val in r.values())
            if is_empty:
                skipped_empty += 1
                continue

            row_tuple = tuple(str(r.get(col)).strip() for col in headers)
            if row_tuple in seen_rows:
                skipped_dup += 1
                continue
            seen_rows.add(row_tuple)
            unique_records.append(r)

        logger.info(
            f"Row statistics: Total read={rows_read}, "
            f"Skipped empty={skipped_empty}, Skipped duplicates={skipped_dup}, "
            f"Unique rows to insert={len(unique_records)}"
        )

        # 11. Map records to insertion rows
        insert_rows = []
        for record in unique_records:
            row_data = []
            for orig_col in headers:
                val = record.get(orig_col)
                if val is None or str(val).strip() == "":
                    val = None
                else:
                    val = str(val).strip()
                row_data.append(val)
            insert_rows.append(row_data)

        # 12. Batch insert rows
        batch_size = 50
        inserted_count = 0
        insert_errors = []
        placeholders = ", ".join(["?"] * len(normalized_cols))
        columns_joined = ", ".join(normalized_cols)

        for i in range(0, len(insert_rows), batch_size):
            batch = insert_rows[i:i + batch_size]
            values_placeholders = []
            params = []
            for row in batch:
                values_placeholders.append(f"({placeholders})")
                params.extend(row)

            sql = f"INSERT INTO {table_name} ({columns_joined}) VALUES {', '.join(values_placeholders)}"
            try:
                await d1_client.execute(sql, params)
                inserted_count += len(batch)
            except Exception as e:
                err_msg = f"Failed to insert batch starting at row {i}: {e}"
                logger.error(err_msg)
                insert_errors.append(err_msg)

        if insert_errors:
            logger.warning(f"Batch insertions completed with {len(insert_errors)} batch failures.")

        # 13. Verification Step
        verify_table_sql = "SELECT name FROM sqlite_master WHERE type='table' AND name = ?"
        verify_res = await d1_client.execute(verify_table_sql, [table_name])
        results = verify_res.get("results", [])
        table_exists = any(r.get("name") == table_name for r in results)

        if not table_exists:
            raise RuntimeError(f"Table verification failed: Table '{table_name}' does not exist in D1 after creation.")

        count_res = await d1_client.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
        db_count = 0
        if count_res and count_res.get("results"):
            db_count = count_res["results"][0].get("cnt", 0)

        logger.info(f"Verified Table '{table_name}': Exists=True, DB Row Count={db_count}, Expected={inserted_count}")

        # 14. Write/Update metadata record in imported_datasets
        meta_upsert_sql = """
        INSERT OR REPLACE INTO imported_datasets (
            spreadsheet_id,
            spreadsheet_title,
            worksheet_name,
            table_name,
            row_count,
            last_synced_at
        ) VALUES (?, ?, ?, ?, ?, ?);
        """
        last_synced_at = datetime.now(timezone.utc).isoformat()
        await d1_client.execute(
            meta_upsert_sql,
            [
                spreadsheet_id,
                spreadsheet_title,
                worksheet_name,
                table_name,
                inserted_count,
                last_synced_at
            ]
        )
        logger.info(f"Updated metadata in imported_datasets for spreadsheet_id '{spreadsheet_id}'.")

        # 15. In-memory registry update
        _sheet_registry[spreadsheet_id] = {
            "spreadsheet_id": spreadsheet_id,
            "title": spreadsheet_title,
            "url": sheet_url,
            "worksheets": [{"title": ws.title, "id": ws.id, "row_count": ws.row_count, "col_count": ws.col_count} for ws in worksheets],
            "last_fetched_at": last_synced_at
        }

        # 16. Clear Caches to update schemas for Text-to-SQL immediately
        logger.info("Invalidating database metadata and LLM schema builder caches...")
        metadata_service.clear_cache()
        schema_builder.invalidate()

        duration = time.perf_counter() - start_time
        logger.info(
            f"Google Sheet connection and sync completed successfully in {duration:.3f}s. "
            f"Action={action}, Imported {inserted_count} rows into '{table_name}'."
        )

        return {
            "success": True,
            "spreadsheet_title": spreadsheet_title,
            "worksheet_name": worksheet_name,
            "table_name": table_name,
            "rows_imported": inserted_count,
            "action": action
        }
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"Google Sheet connect and sync failed after {duration:.3f}s: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


from datetime import datetime, timezone

def fetch_sheet_data(
    spreadsheet_id: str = None,
    sheet_url: str = None,
    worksheet_name: str = None,
    max_rows: int = 50,
) -> dict:
    """
    Fetch live rows from a connected Google Sheet. Returns rows as a list of dicts keyed by column headers.
    Either spreadsheet_id or sheet_url must be provided.
    """
    try:
        # Determine the spreadsheet ID
        target_id = spreadsheet_id
        if not target_id and sheet_url:
            target_id = _extract_spreadsheet_id(sheet_url)
            
        if not target_id:
            raise ValueError("Either spreadsheet_id or sheet_url must be provided.")

        target_ws_name = worksheet_name

        logger.info(
            f"Fetching data for sheet ID: {target_id}, worksheet: {target_ws_name}, max_rows: {max_rows}"
        )
        
        client = get_gspread_client()
        spreadsheet = client.open_by_key(target_id)
        
        if target_ws_name:
            logger.info(f"Accessing worksheet: {target_ws_name}")
            try:
                ws = spreadsheet.worksheet(target_ws_name)
            except gspread.exceptions.WorksheetNotFound:
                if target_ws_name == "Sheet1":
                    logger.info("Worksheet 'Sheet1' not found, falling back to the first worksheet (sheet1)")
                    ws = spreadsheet.sheet1
                else:
                    raise
        else:
            logger.info("No worksheet name provided, defaulting to the first worksheet (sheet1)")
            ws = spreadsheet.sheet1
            
        logger.info("Reading records from worksheet")
        records = ws.get_all_records()
        
        # Apply max_rows limit
        if max_rows is not None and max_rows > 0:
            records = records[:max_rows]
        
        if target_id in _sheet_registry:
            _sheet_registry[target_id]["last_fetched_at"] = datetime.now(timezone.utc).isoformat()
            
        logger.info(f"Successfully fetched {len(records)} rows from worksheet '{ws.title}'")
        return {
            "worksheet": ws.title,
            "row_count": len(records),
            "data": records
        }
    except Exception as e:
        logger.error(f"Failed to fetch Google Sheet data: {e}", exc_info=True)
        return {
            "error": str(e)
        }


def normalize_column_name(header: str, index: int) -> str:
    """
    Sanitizes sheet column headers to clean, database-safe column names.
    Replaces spaces/special characters with underscores, ensures lowercase, collapses duplicates,
    and prepends prefix if starting with a number.
    """
    name = str(header).strip()
    if not name:
        return f"col_{index}"
        
    name = name.lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    
    if name and name[0].isdigit():
        name = f"col_{name}"
        
    return name or f"col_{index}"


def normalize_table_name(title: str) -> str:
    """
    Sanitizes worksheet titles to clean database-safe table names.
    """
    name = str(title).strip().lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    if name and name[0].isdigit():
        name = f"tbl_{name}"
    return name or "imported_table"


def infer_column_type(values: list) -> str:
    """
    Infers the SQLite compatible type affinity (INTEGER, REAL, DATE, TEXT)
    from a list of cell values for a column.
    """
    non_empty_vals = [str(v).strip() for v in values if v is not None and str(v).strip() != ""]
    if not non_empty_vals:
        return "TEXT"
        
    is_int = True
    is_real = True
    is_date = True
    
    date_patterns = [
        r'^\d{4}-\d{2}-\d{2}$',
        r'^\d{4}/\d{2}/\d{2}$',
        r'^\d{2}-\d{2}-\d{4}$',
        r'^\d{2}/\d{2}/\d{4}$'
    ]
    
    for val in non_empty_vals:
        if is_int:
            if not re.match(r'^[-+]?\d+$', val):
                is_int = False
                
        if is_real:
            if not re.match(r'^[-+]?\d*\.\d+$', val) and not re.match(r'^[-+]?\d+$', val):
                is_real = False
                
        if is_date:
            matched_date = False
            for pattern in date_patterns:
                if re.match(pattern, val):
                    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
                        try:
                            datetime.strptime(val, fmt)
                            matched_date = True
                            break
                        except ValueError:
                            continue
                if matched_date:
                    break
            if not matched_date:
                is_date = False
                
    if is_int:
        return "INTEGER"
    elif is_real:
        return "REAL"
    elif is_date:
        return "DATE"
    else:
        return "TEXT"


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
    Infers database schema from a Google Sheet worksheet, creates a table in Cloudflare D1,
    cleans/deduplicates rows, batch inserts them, and invalidates schema caches.
    """
    import time

    start_time = time.perf_counter()
    logger.info(
        f"Starting sheet ingestion to D1: spreadsheet_id={spreadsheet_id}, "
        f"worksheet_title={worksheet_title}, table_name={table_name}, overwrite={overwrite}"
    )

    try:
        # 1. Fetch sheet data (None or 0 max_rows fetches everything)
        sheet_data = fetch_sheet_data(
            spreadsheet_id=spreadsheet_id,
            sheet_url=sheet_url,
            worksheet_name=worksheet_name or worksheet_title,
            max_rows=max_rows
        )

        if "error" in sheet_data:
            raise ValueError(f"Failed to fetch sheet data: {sheet_data['error']}")

        records = sheet_data.get("data", [])
        actual_worksheet_title = sheet_data.get("worksheet", "Sheet1")
        rows_read = len(records)
        logger.info(f"Read {rows_read} raw rows from worksheet '{actual_worksheet_title}'")

        if not records:
            raise ValueError("No records found in the worksheet. Cannot import an empty sheet.")

        # Get headers from first record keys
        headers = list(records[0].keys())
        if not headers:
            raise ValueError("No columns/headers found in the worksheet.")

        # 2. Determine target table name
        if not table_name:
            table_name = normalize_table_name(actual_worksheet_title)
        else:
            table_name = normalize_table_name(table_name)

        logger.info(f"Target table name: '{table_name}'")

        # 3. Normalize column names and infer types
        normalized_cols = []
        seen_cols = set()
        for idx, col in enumerate(headers):
            norm = normalize_column_name(col, idx)
            original_norm = norm
            counter = 1
            while norm in seen_cols:
                norm = f"{original_norm}_{counter}"
                counter += 1
            seen_cols.add(norm)
            normalized_cols.append(norm)

        # Infer types for each column
        inferred_types = []
        for col in headers:
            col_values = [r.get(col) for r in records]
            inferred_types.append(infer_column_type(col_values))

        # 4. Build D1 table schema definition
        col_defs = []
        for col_name, col_type in zip(normalized_cols, inferred_types):
            col_defs.append(f"{col_name} {col_type}")

        create_table_sql = f"CREATE TABLE {table_name} ({', '.join(col_defs)});"

        # 5. Execute D1 table creation
        d1_client = D1Client()
        if overwrite:
            logger.info(f"Dropping existing table if exists: '{table_name}'")
            await d1_client.execute(f"DROP TABLE IF EXISTS {table_name}")

        logger.info(f"Creating D1 table with SQL: {create_table_sql}")
        await d1_client.execute(create_table_sql)

        # 6. Filter empty rows and deduplicate records
        unique_records = []
        seen_rows = set()
        skipped_empty = 0
        skipped_dup = 0

        for r in records:
            is_empty = all(val is None or str(val).strip() == "" for val in r.values())
            if is_empty:
                skipped_empty += 1
                continue

            row_tuple = tuple(str(r.get(col)).strip() for col in headers)
            if row_tuple in seen_rows:
                skipped_dup += 1
                continue
            seen_rows.add(row_tuple)
            unique_records.append(r)

        logger.info(
            f"Row statistics: Total read={rows_read}, "
            f"Skipped empty={skipped_empty}, Skipped duplicates={skipped_dup}, "
            f"Unique rows to insert={len(unique_records)}"
        )

        # 7. Map records to insertion rows
        insert_rows = []
        for record in unique_records:
            row_data = []
            for orig_col in headers:
                val = record.get(orig_col)
                if val is None or str(val).strip() == "":
                    val = None
                else:
                    val = str(val).strip()
                row_data.append(val)
            insert_rows.append(row_data)

        # 8. Batch insert rows
        batch_size = 50
        inserted_count = 0
        insert_errors = []
        placeholders = ", ".join(["?"] * len(normalized_cols))
        columns_joined = ", ".join(normalized_cols)

        for i in range(0, len(insert_rows), batch_size):
            batch = insert_rows[i:i + batch_size]
            values_placeholders = []
            params = []
            for row in batch:
                values_placeholders.append(f"({placeholders})")
                params.extend(row)

            sql = f"INSERT INTO {table_name} ({columns_joined}) VALUES {', '.join(values_placeholders)}"
            try:
                await d1_client.execute(sql, params)
                inserted_count += len(batch)
            except Exception as e:
                err_msg = f"Failed to insert batch starting at row {i}: {e}"
                logger.error(err_msg)
                insert_errors.append(err_msg)

        if insert_errors:
            logger.warning(f"Batch insertions completed with {len(insert_errors)} batch failures.")

        # 9. Verification Step
        verify_table_sql = "SELECT name FROM sqlite_master WHERE type='table' AND name = ?"
        verify_res = await d1_client.execute(verify_table_sql, [table_name])
        results = verify_res.get("results", [])
        table_exists = any(r.get("name") == table_name for r in results)

        if not table_exists:
            raise RuntimeError(f"Table verification failed: Table '{table_name}' does not exist in D1 after creation.")

        count_res = await d1_client.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
        db_count = 0
        if count_res and count_res.get("results"):
            db_count = count_res["results"][0].get("cnt", 0)

        logger.info(f"Verified Table '{table_name}': Exists=True, DB Row Count={db_count}, Expected={inserted_count}")

        # 10. Clear Caches to update schemas for Text-to-SQL immediately
        logger.info("Invalidating database metadata and LLM schema builder caches...")
        metadata_service.clear_cache()
        schema_builder.invalidate()

        duration = time.perf_counter() - start_time
        logger.info(
            f"Ingestion pipeline completed successfully in {duration:.3f}s. "
            f"Imported {inserted_count} rows into '{table_name}'."
        )

        return {
            "success": True,
            "table_name": table_name,
            "rows_imported": inserted_count,
            "columns": len(normalized_cols),
            "verification": {
                "table_exists": table_exists,
                "db_row_count": db_count
            },
            "errors": insert_errors
        }

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"Sheet ingestion failed after {duration:.3f}s: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
