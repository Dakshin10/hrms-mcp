import os
from src.core.logging.logger import logger
from src.services.database.metadata_service import metadata_service
from src.services.database.query_service import query_service
from src.services.ai.text_to_sql import ask
from src.services.ai import sql_validator, schema_builder, query_cache

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
