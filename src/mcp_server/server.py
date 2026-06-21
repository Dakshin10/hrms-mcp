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

mcp = FastMCP("Minori Database Assistant")

d1_client = D1Client()
timesheet_loader = TimesheetLoader(d1_client)
hr_handler = HRInsightsHandler()


@mcp.tool()
async def list_tables():
    """
    List all available tables.
    """
    logger.info("MCP Tool list_tables invoked")
    tables = await metadata_service.get_tables()
    return tables


@mcp.tool()
async def describe_table(table_name: str):
    """
    Get schema information for a table.
    """
    logger.info(f"MCP Tool describe_table invoked for: {table_name}")
    schema = await metadata_service.get_table_schema(table_name)
    return schema


@mcp.tool()
async def execute_sql(sql: str):
    """
    Execute read-only SQL queries.
    """
    logger.info("MCP Tool execute_sql invoked")
    try:
        known_schema = await schema_builder.get_full_schema()
        sql_validator.validate(sql, known_schema)
    except SQLValidationError as e:
        logger.error(f"Manual SQL execution validation failed: {e}")
        return {"error": f"SQL validation failed: {e}"}

    try:
        result = await query_service.execute_query(sql)
        return result
    except Exception as e:
        logger.error(f"Manual SQL execution failed on database: {e}")
        return {"error": f"Database execution failed: {e}"}


@mcp.tool()
async def load_timesheets(file_path: str) -> str:
    """
    Ingest a real timesheet export (CSV or Excel) and load it into the database.
    """
    logger.info(f"MCP Tool load_timesheets invoked with path: {file_path}")
    summary = await timesheet_loader.load_file(file_path)
    if summary.get("errors"):
        logger.error(f"Timesheet loading errors: {summary['errors']}")

    return (
        f"Loaded {summary['loaded']} of {summary['total_rows']} rows from {summary['file']}. "
        f"Skipped {summary['skipped']} invalid rows."
    )


@mcp.tool()
async def hr_insights(question: str) -> str:
    """
    Ask natural language HR questions (e.g. top performers, star employees, department rankings, rework rates).
    """
    logger.info(f"MCP Tool hr_insights invoked with question: '{question}'")
    answer = await hr_handler.handle(question)
    return answer


@mcp.tool()
async def cache_stats() -> str:
    """
    Returns current query cache statistics.
    """
    logger.info("MCP Tool cache_stats invoked")
    stats = query_cache.stats()
    return f"Cached queries: {stats['cached_queries']}"


@mcp.tool()
async def ask_database(question: str) -> str:
    """
    Ask a natural language question about the database.
    """
    logger.info(f"MCP Tool ask_database invoked with question: '{question}'")
    result = await ask(question)

    answer = result.get("answer", "")
    generated_sql = result.get("generated_sql", "")
    results = result.get("results", [])

    return f"""{answer}

--- Debug ---
SQL: {generated_sql}
Raw results: {results}"""


@mcp.tool()
async def hr_agent(question: str, session_id: str = "default") -> str:
    """
    Multi-step HR agent. Use this for complex questions that require
    combining data from multiple sources or multiple analytical steps.
    
    Examples:
    - Compare all departments and tell me which needs attention
    - Give me a full performance summary for this month  
    - Who should be recognized and who needs coaching?
    - What is the overall health of the organization?
    """
    from src.agent.hr_agent import HRAgent
    from src.agent.conversation_memory import memory_store
    
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


@mcp.tool()
async def clear_session(session_id: str = "default") -> str:
    """Clears conversation memory for a session."""
    from src.agent.conversation_memory import memory_store
    memory_store.clear_session(session_id)
    return f"Session {session_id} cleared."


if __name__ == "__main__":
    logger.info("Starting Minori HRMS MCP Server...")
    mcp.run()