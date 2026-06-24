import time
from src.core.logging.logger import logger
from src.core.exceptions.errors import SQLValidationError
from src.services.database.query_service import query_service
from src.services.ai import (
    table_selector,
    schema_builder,
    prompt_builder,
    llm_service,
    sql_validator,
    query_cache,
    fast_path_handler,
    query_observer
)
from src.services.ai.answer_generator import generate_answer
from src.services.ai.observability import QueryTrace


async def question_to_sql(question: str) -> tuple[str, dict, list[str], dict]:
    """
    Orchestrates the Text-to-SQL SQL generation.
    1. Identifies relevant tables.
    2. Builds the minimal schema context.
    3. Renders the prompt.
    4. Calls the LLM asynchronously.
    Returns:
        tuple: (generated_sql, llm_metrics, selected_tables, schema_dict)
    """
    selected_tables = table_selector.select_tables(question)
    schema = await schema_builder.get_schema_for_tables(selected_tables)
    schema_str = schema_builder.get_schema_as_prompt_string(schema)

    system_prompt = prompt_builder.get_system_prompt()
    user_prompt = prompt_builder.build_user_prompt(question, schema_str)

    sql, llm_metrics = await llm_service.generate_sql(system_prompt, user_prompt)
    return sql, llm_metrics, selected_tables, schema


async def ask(question: str) -> dict:
    """
    Main ask() pipeline with Fast Path, cache, validation, execution, and NL answers.
    """
    # 1. Try Fast Path
    fast_result = await fast_path_handler.try_handle(question)
    if fast_result:
        logger.info("Fast path query hit")
        return fast_result

    # 2. Check Query Cache
    cached = query_cache.get(question)
    if cached:
        logger.info("Query cache query hit")
        return cached

    # 3. Full LLM Pipeline
    start_time = time.perf_counter()
    sql = ""
    selected_tables = []
    llm_metrics = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": 0.0,
        "model_used": "unknown"
    }
    d1_start = 0.0
    d1_latency_ms = 0.0
    results = []
    validation_passed = False
    validation_error = None
    exec_error = None

    try:
        sql, llm_metrics, selected_tables, schema_dict = await question_to_sql(question)

        try:
            sql_validator.validate(sql, schema_dict)
            validation_passed = True
        except SQLValidationError as e:
            validation_error = str(e)
            logger.warning(f"SQL validation error: {e}")
            raise

        d1_start = time.perf_counter()
        results = await query_service.execute_query(sql)
        d1_latency_ms = (time.perf_counter() - d1_start) * 1000.0

    except SQLValidationError as e:
        logger.warning(f"SQL validation blocked: {e}")
        return {
            "generated_sql": None,
            "results": [],
            "answer": (
                "That operation is not permitted. "
                "Only read-only SELECT queries are allowed. "
                "If you meant to retrieve data, please rephrase "
                "your question."
            ),
            "blocked": True
        }
    except Exception as e:
        if d1_start > 0.0 and d1_latency_ms == 0.0:
            d1_latency_ms = (time.perf_counter() - d1_start) * 1000.0
        exec_error = str(e)

    # 4. Generate Natural Language Answer
    answer = ""
    if validation_passed and not exec_error:
        try:
            answer = await generate_answer(question, sql, results)
        except Exception as e:
            logger.error(f"Failed to generate natural language answer: {e}")
            answer = "No response could be formulated."
    else:
        answer = f"Failed to answer question: {exec_error or validation_error}"

    # Record Observability Trace
    total_latency_ms = (time.perf_counter() - start_time) * 1000.0
    row_count = len(results) if isinstance(results, list) else 0

    trace = QueryTrace(
        question=question,
        selected_tables=selected_tables,
        generated_sql=sql,
        validation_passed=validation_passed,
        validation_error=validation_error,
        d1_latency_ms=d1_latency_ms,
        llm_latency_ms=llm_metrics.get("latency_ms", 0.0),
        total_latency_ms=total_latency_ms,
        prompt_tokens=llm_metrics.get("prompt_tokens", 0),
        completion_tokens=llm_metrics.get("completion_tokens", 0),
        total_tokens=llm_metrics.get("total_tokens", 0),
        row_count=row_count,
        error=exec_error
    )
    query_observer.log_trace(trace)

    result_dict = {
        "generated_sql": sql,
        "results": results,
        "answer": answer,
        "fast_path": False
    }

    # Cache successful outputs
    if validation_passed and not exec_error:
        query_cache.set(question, result_dict)

    return result_dict