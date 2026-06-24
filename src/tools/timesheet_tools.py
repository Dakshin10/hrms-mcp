from pathlib import Path
from src.core.logging.logger import logger
from src.services.database.d1_client import D1Client
from src.services.database.sync.timesheet_loader import TimesheetLoader

d1_client = D1Client()
timesheet_loader = TimesheetLoader(d1_client)

async def load_timesheets(file_path: str) -> str | dict:
    """
    Ingest a real timesheet export (CSV or Excel) and load it into the database.
    """
    logger.info(f"MCP Tool load_timesheets invoked with path: {file_path}")
    try:
        base_dir = Path("./data/imports").resolve()
        target_path = Path(file_path).resolve()

        try:
            target_path.relative_to(base_dir)
        except ValueError:
            raise ValueError(f"Access denied: Path '{file_path}' resolves outside the allowed base directory '{base_dir}'.")

        summary = await timesheet_loader.load_file(str(target_path))
        if summary.get("errors"):
            logger.error(f"Timesheet loading errors: {summary['errors']}")

        return (
            f"Loaded {summary['loaded']} of {summary['total_rows']} rows from {summary['file']}. "
            f"Skipped {summary['skipped']} invalid rows."
        )
    except Exception as e:
        logger.error(f"Error in load_timesheets: {e}")
        return {"error": str(e), "tool": "load_timesheets"}
