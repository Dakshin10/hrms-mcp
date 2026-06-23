import os
import sys
from pathlib import Path

# Add project root to python path to resolve absolute imports when run directly
sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))

from mcp.server.fastmcp import FastMCP
from src.core.logging.logger import logger
from src.core.exceptions.errors import SQLValidationError
from src.database.d1_client import D1Client
from src.services.metadata.metadata_service import metadata_service
from src.services.query.query_service import query_service
from src.services.text_to_sql import ask
from src.services.ai import sql_validator, schema_builder, query_cache
from src.services.sync.timesheet_loader import TimesheetLoader
from src.mcp_server.tools.hr.hr_insights_handler import HRInsightsHandler
from src.agent.hr_agent import HRAgent
from src.agent.conversation_memory import memory_store
from src.services.google_sheets_service import connect_google_sheet, fetch_sheet_data

mcp = FastMCP("Minori Database Assistant")

d1_client = D1Client()
timesheet_loader = TimesheetLoader(d1_client)
hr_handler = HRInsightsHandler()


@mcp.tool()
async def list_tables() -> list | dict:
    """
    List all available tables.
    """
    logger.info("MCP Tool list_tables invoked")
    try:
        tables = await metadata_service.get_tables()
        return tables
    except Exception as e:
        logger.error(f"Error in list_tables: {e}")
        return {"error": str(e), "tool": "list_tables"}


@mcp.tool()
async def describe_table(table_name: str) -> dict:
    """
    Get schema information for a table.
    """
    logger.info(f"MCP Tool describe_table invoked for: {table_name}")
    try:
        schema = await metadata_service.get_table_schema(table_name)
        return schema
    except Exception as e:
        logger.error(f"Error in describe_table: {e}")
        return {"error": str(e), "tool": "describe_table"}


@mcp.tool()
async def execute_sql(sql: str) -> list | dict:
    """
    Execute read-only SQL queries.
    """
    logger.info("MCP Tool execute_sql invoked")
    try:
        known_schema = await schema_builder.get_full_schema()
        sql_validator.validate(sql, known_schema)
        result = await query_service.execute_query(sql)
        return result
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        return {"error": str(e), "tool": "execute_sql"}


@mcp.tool()
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


@mcp.tool()
async def hr_insights(question: str) -> str | dict:
    """
    Ask natural language HR questions (e.g. top performers, star employees, department rankings, rework rates).
    
    Use this tool when:
    - The question involves HR analytics, performance metrics, department rankings, or timesheet statistics.
    - The question contains keywords related to:
      * top/best/highest/star/performer/leading (top_performers)
      * bottom/low/worst/struggling/underperform/below (bottom_performers)
      * attention/risk/flag/help/needs/concern/problem (employees needing attention)
      * department/team/group/division/which dept/dept rank (department KPI ranking)
      * eta/deadline/late/missed/on time/delay/overdue (timesheet ETA adherence)
      * ftr/rework/first time/quality/redo/correction (First Time Right / rework rates)
      * utilization/billable/hours/capacity/workload (employee utilization)
    
    Routing criteria:
    - Specifically optimized for parsing dates (month/year) and routing to analytical services.
    - Falls back to database ask if no keywords are matched.
    """
    logger.info(f"MCP Tool hr_insights invoked with question: '{question}'")
    try:
        answer = await hr_handler.handle(question)
        return answer
    except Exception as e:
        logger.error(f"Error in hr_insights: {e}")
        return {"error": str(e), "tool": "hr_insights"}


@mcp.tool()
async def cache_stats() -> str | dict:
    """
    Returns current query cache statistics.
    """
    logger.info("MCP Tool cache_stats invoked")
    try:
        stats = query_cache.stats()
        cached_queries = stats.get("cached_queries", 0)
        total_queries = stats.get("total_queries", 0)
        hits = stats.get("hits", 0)
        misses = stats.get("misses", 0)
        hit_rate = stats.get("hit_rate", 0.0)

        return (
            f"Cached queries: {cached_queries}\n"
            f"Total queries: {total_queries}\n"
            f"Cache hits: {hits}\n"
            f"Cache misses: {misses}\n"
            f"Hit rate: {hit_rate:.2f}%"
        )
    except Exception as e:
        logger.error(f"Error in cache_stats: {e}")
        return {"error": str(e), "tool": "cache_stats"}


@mcp.tool()
async def ask_database(question: str) -> str | dict:
    """
    Ask a natural language question about the database.
    
    Use this tool when:
    - You need to perform direct SQL-level queries or arbitrary database questions.
    - The question is about table metadata, specific schemas, or data not covered by high-level HR analytics routes.
    - No HR-specific keywords (like top performers, utilization, FTR, rework, department rankings) are present in the question.
    
    Routing criteria:
    - Direct fallback for general database questions that do not match predefined HR metrics.
    """
    logger.info(f"MCP Tool ask_database invoked with question: '{question}'")
    try:
        result = await ask(question)

        answer = result.get("answer", "")
        
        debug_mode_str = os.environ.get("DEBUG_MODE", "False")
        debug_mode = debug_mode_str.lower() in ("true", "1", "t", "y", "yes")

        if debug_mode:
            generated_sql = result.get("generated_sql", "")
            results = result.get("results", [])
            return f"""{answer}

--- Debug ---
SQL: {generated_sql}
Raw results: {results}"""
        else:
            return answer
    except Exception as e:
        logger.error(f"Error in ask_database: {e}")
        return {"error": str(e), "tool": "ask_database"}


@mcp.tool()
async def hr_agent(question: str, session_id: str) -> str | dict:
    """
    Multi-step HR agent. Use this for complex questions that require
    combining data from multiple sources or multiple analytical steps.
    
    Examples:
    - Compare all departments and tell me which needs attention
    - Give me a full performance summary for this month  
    - Who should be recognized and who needs coaching?
    - What is the overall health of the organization?
    """
    logger.info(f"MCP Tool hr_agent invoked with question: '{question}', session_id: '{session_id}'")
    try:
        if not session_id or not session_id.strip():
            return "Error: session_id is required and cannot be empty."

        session = memory_store.get_or_create(session_id)
        agent = HRAgent()
        
        result = await agent.ask(
            question=question,
            history=session.get_history(last_n_turns=5)
        )
        
        session.add_turn(question, result["answer"])
        
        steps_info = ""
        if result["steps"] > 1:
            steps_info = (
                f"\n\n[Used {result['steps']} analysis steps: "
                f"{', '.join(result['tools_used'])}]"
            )
        
        return result["answer"] + steps_info
    except Exception as e:
        logger.error(f"Error in hr_agent: {e}")
        return {"error": str(e), "tool": "hr_agent"}


@mcp.tool()
async def clear_session(session_id: str = "default") -> str | dict:
    """Clears conversation memory for a session."""
    logger.info(f"MCP Tool clear_session invoked for: {session_id}")
    try:
        memory_store.clear_session(session_id)
        return f"Session {session_id} cleared."
    except Exception as e:
        logger.error(f"Error in clear_session: {e}")
        return {"error": str(e), "tool": "clear_session"}


mcp.tool()(connect_google_sheet)
mcp.tool()(fetch_sheet_data)


if __name__ == "__main__":
    logger.info("Starting Minori HRMS MCP Server...")
    mcp.run()