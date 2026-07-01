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
    selected_tables = await table_selector.select_tables(question)
    schema = await schema_builder.get_schema_for_tables(selected_tables)
    schema_str = schema_builder.get_schema_as_prompt_string(schema)

    # Discover relationships dynamically
    from src.services.ai.schema_builder import discover_relationships
    relationships = discover_relationships(schema)

    # --- Pipeline Logging ---
    logger.info("=" * 60)
    logger.info(f"QUESTION: {question}")
    logger.info(f"DISCOVERED TABLES: {selected_tables}")
    for t_name, cols in schema.items():
        col_names = [c.get('name', '') for c in cols]
        logger.info(f"DISCOVERED COLUMNS [{t_name}]: {col_names}")
    if relationships:
        logger.info("RELATIONSHIPS: " + " | ".join(relationships))
    logger.info("SCHEMA CONTEXT:\n" + schema_str)
    logger.info("=" * 60)

    system_prompt = prompt_builder.get_system_prompt()
    user_prompt = prompt_builder.build_user_prompt(question, schema_str, relationships)

    sql, llm_metrics = await llm_service.generate_sql(system_prompt, user_prompt)
    logger.info(f"GENERATED SQL: {sql}")
    return sql, llm_metrics, selected_tables, schema


async def self_heal_sql(
    question: str,
    failed_sql: str,
    error_message: str,
    schema_dict: dict
) -> tuple[str, dict]:
    """
    Regenerates SQL query by passing the previous failed SQL and error message back to the LLM.
    """
    schema_str = schema_builder.get_schema_as_prompt_string(schema_dict)
    
    # Discover relationships dynamically
    from src.services.ai.schema_builder import discover_relationships
    relationships = discover_relationships(schema_dict)
    relationships_str = "\n## Relationships / Join Candidates (use these for JOINs):\n" + "\n".join(relationships) if relationships else ""

    system_prompt = prompt_builder.get_system_prompt()
    
    user_prompt = f"""## Available Schema (ONLY use these tables and columns):

{schema_str}
{relationships_str}

## Previous Attempt:
Failed SQL: {failed_sql}
Error Received: {error_message}

## User Question:
{question}

## Correction Task:
The previous SQL query failed. Analyze the error message and the available schema.
1. Identify the incorrect table or column names, or syntax issues.
2. Correct the query using ONLY the valid tables and columns listed in the schema.
3. If columns like first_name/last_name/employee_email do not exist, use existing columns like employee_name/employee_id instead.
4. Output ONLY the corrected raw SELECT or WITH query. Do not write markdown, code blocks, or explanations.
"""
    sql, metrics = await llm_service.generate_sql(system_prompt, user_prompt)
    return sql, metrics


async def ask(question: str) -> dict:
    """
    Main ask() pipeline with Fast Path, cache, validation, execution, self-healing retries, and NL answers.
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

    # 3. Full LLM Pipeline with Self-Healing Loop
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

    max_attempts = 3
    attempt = 0
    feedback_msg = ""
    schema_dict = {}

    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Text-to-SQL generation attempt {attempt}/{max_attempts}...")
        
        try:
            if attempt == 1:
                # First attempt: standard generation
                sql, first_metrics, selected_tables, schema_dict = await question_to_sql(question)
                llm_metrics.update(first_metrics)
            else:
                # Self-healing attempt: pass previous error feedback
                logger.info(f"Self-healing trigger: Regenerating SQL due to previous failure: {feedback_msg}")

                # If the error mentions an unknown/missing table, reload the FULL schema
                # so the LLM has visibility of ALL available tables on retry.
                if "unknown table" in feedback_msg.lower() or "no such table" in feedback_msg.lower():
                    try:
                        full_schema = await schema_builder.get_full_schema()
                        schema_dict = full_schema
                        selected_tables = list(full_schema.keys())
                        logger.info(
                            f"[SelfHeal] Unknown-table error detected. Expanding schema to ALL tables: "
                            f"{selected_tables}"
                        )
                        # Log expanded columns for diagnostics
                        for t_name, cols in full_schema.items():
                            col_names = [c.get('name', '') for c in cols]
                            logger.info(f"[SelfHeal] COLUMNS [{t_name}]: {col_names}")
                    except Exception as schema_err:
                        logger.warning(f"[SelfHeal] Failed to reload full schema: {schema_err}")

                sql, healing_metrics = await self_heal_sql(question, sql, feedback_msg, schema_dict)
                logger.info(f"[SelfHeal] Regenerated SQL (attempt {attempt}): {sql}")
                # Combine metrics
                for k, v in healing_metrics.items():
                    if k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        llm_metrics[k] = llm_metrics.get(k, 0) + v
                    elif k == "latency_ms":
                        llm_metrics[k] = llm_metrics.get(k, 0.0) + v
                    elif k == "model_used":
                        llm_metrics[k] = v

            # Validate generated SQL
            try:
                sql_validator.validate(sql, schema_dict)
                validation_passed = True
                validation_error = None
                logger.info(f"VALIDATED SQL: {sql}")
            except SQLValidationError as e:
                validation_passed = False
                validation_error = str(e)
                logger.warning(f"SQL validation failed on attempt {attempt}: {e}")
                feedback_msg = f"SQL Validation Error: {e}"
                continue

            # Execute query on D1
            d1_start = time.perf_counter()
            try:
                results = await query_service.execute_query(sql)
                d1_latency_ms = (time.perf_counter() - d1_start) * 1000.0
                exec_error = None
                logger.info(f"EXECUTED SQL: {sql}")
                logger.info(f"RESULT COUNT: {len(results) if isinstance(results, list) else 'N/A'}")
                break  # Succeeded! Exit retry loop.
            except Exception as e:
                d1_latency_ms = (time.perf_counter() - d1_start) * 1000.0
                exec_error = str(e)
                logger.warning(f"SQL execution failed on D1 on attempt {attempt}: {e}")
                feedback_msg = f"Database SQLite Error: {e}"
                continue
                
        except Exception as gen_err:
            logger.error(f"Unexpected generation error on attempt {attempt}: {gen_err}")
            exec_error = str(gen_err)
            break

    # 4. Generate Natural Language Answer
    answer = ""
    if validation_passed and not exec_error:
        try:
            answer = await generate_answer(question, sql, results)
        except Exception as e:
            logger.error(f"Failed to generate natural language answer: {e}")
            answer = "No response could be formulated."
    else:
        # Convert raw SQL/execution errors to friendly explanations
        friendly_err = exec_error or validation_error
        if friendly_err:
            if "no such column" in friendly_err.lower():
                answer = f"Sorry, I could not retrieve that information because the query referenced columns that do not exist in the database. Error detail: {friendly_err}"
            elif "no such table" in friendly_err.lower():
                answer = f"Sorry, I could not retrieve that information because the referenced table was not found in the database. Error detail: {friendly_err}"
            else:
                answer = f"Sorry, I encountered a validation or database error while executing the query: {friendly_err}"
        else:
            answer = "Failed to answer question due to generation failure."

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
        "rows_returned": row_count,
        "execution_time_ms": total_latency_ms,
        "structured_data": results,
        "answer": answer,
        "success": exec_error is None and validation_passed
    }

    # Cache successful outputs
    if validation_passed and not exec_error:
        query_cache.set(question, result_dict)

    return result_dict