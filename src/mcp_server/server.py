import os
import sys
from pathlib import Path

# Add project root to python path to resolve absolute imports when run directly
sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))

from mcp.server.fastmcp import FastMCP
from src.core.logging.logger import logger

from src.tools.db_tools import list_tables, describe_table, execute_sql, ask_database, cache_stats
from src.tools.employee_tools import get_all_employees, get_employee_by_id, get_employees_by_department, search_employees
from src.tools.hr_tools import hr_insights, hr_agent, clear_session, health_groq
from src.tools.sheet_tools import connect_google_sheet, fetch_sheet_data, health_google_sheets, import_sheet_data
from src.tools.timesheet_tools import load_timesheets
from src.config.google_config import get_credentials_dir, get_client_secret_path

# Initialize FastMCP Server
mcp = FastMCP("Minori Database Assistant")

# Run Google Sheets startup validation
def _validate_google_sheets_setup():
    cred_dir = get_credentials_dir()
    secret_path = get_client_secret_path()
    if not cred_dir.exists() or not secret_path.exists():
        logger.warning("Google Sheets integration credentials check failed: missing credentials.")
        logger.warning("Please ensure credentials/client_secret.json is present.")
    else:
        logger.info("Google OAuth credentials loaded successfully.")
        logger.info("Google Sheets integration initialized.")

_validate_google_sheets_setup()


# Register Database Tools
mcp.tool()(list_tables)
mcp.tool()(describe_table)
mcp.tool()(execute_sql)
mcp.tool()(ask_database)
mcp.tool()(cache_stats)

# Register Employee Tools
mcp.tool()(get_all_employees)
mcp.tool()(get_employee_by_id)
mcp.tool()(get_employees_by_department)
mcp.tool()(search_employees)

# Register HR Tools
mcp.tool()(hr_insights)
mcp.tool()(hr_agent)
mcp.tool()(clear_session)
mcp.tool()(health_groq)

# Register Google Sheet Tools
mcp.tool()(connect_google_sheet)
mcp.tool()(fetch_sheet_data)
mcp.tool()(import_sheet_data)
mcp.tool()(health_google_sheets)

# Register Timesheet Tools
mcp.tool()(load_timesheets)

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    logger.info(f"Starting Minori HRMS MCP Server with transport: {transport}...")
    
    if transport == "sse":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8000"))
        logger.info(f"Running SSE server on http://{host}:{port}")
        mcp.run(transport="sse", host=host, port=port)
    else:
        logger.info("Running standard Stdio server")
        mcp.run(transport="stdio")