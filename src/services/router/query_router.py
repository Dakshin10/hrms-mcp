import re
import time
from datetime import datetime
from src.core.logging.logger import logger
from src.services.database.metadata_service import metadata_service

# Import standard tools
from src.tools.db_tools import list_tables, describe_table, execute_sql, ask_database, cache_stats
from src.tools.employee_tools import get_all_employees, get_employee_by_id, get_employees_by_department, search_employees
from src.tools.hr_tools import hr_insights
from src.tools.sheet_tools import connect_google_sheet
from src.tools.timesheet_tools import load_timesheets
from src.agent.fast_path import format_as_markdown_table

# Canonical Table Names and Aliases
TABLE_ALIAS_MAP = {
    "employees": "employees",
    "employee": "employees",
    "employee table": "employees",
    "employee_kpis": "employee_kpis",
    "employee kpis": "employee_kpis",
    "kpis": "employee_kpis",
    "kpi": "employee_kpis",
    "timesheets": "timesheets",
    "timesheet": "timesheets",
    "audit_logs": "audit_logs",
    "audit log": "audit_logs",
    "audit": "audit_logs",
    "import_history": "import_history",
    "imported_datasets": "imported_datasets",
    "task_logs": "task_logs",
    "timesheet_summary": "timesheet_summary"
}

# Prefetch tables into cache on import
import asyncio
try:
    loop = asyncio.get_running_loop()
    loop.create_task(metadata_service.get_tables())
except RuntimeError:
    pass


def resolve_table_name(name: str) -> str | None:
    if not name:
        return None
    cleaned = name.strip().lower()
    return TABLE_ALIAS_MAP.get(cleaned)


async def route_query(question: str) -> dict | None:
    """
    Directly routes user query to MCP tools using regex patterns, template detection,
    and keyword matching, avoiding LangGraph and Groq agent loops.
    """
    start_time = time.perf_counter()
    q = question.strip().lower()
    if q.endswith("?") or q.endswith(";"):
        q = q[:-1].strip()

    tool_name = None
    args = {}
    answer = None
    sql_to_execute = None
    database_query = False

    # 1. list_tables Match
    if q in ("list tables", "show tables", "database tables", "all tables", "what tables are available"):
        tool_name = "list_tables"

    # 2. describe_table Match
    elif "describe table" in q or q.startswith("describe ") or q.startswith("schema ") or q.startswith("info "):
        # Extract table name candidate
        table_candidate = q.replace("describe table", "").replace("describe", "").replace("schema", "").replace("info", "").strip()
        canonical_table = resolve_table_name(table_candidate)
        if canonical_table:
            tool_name = "describe_table"
            args = {"table_name": canonical_table}

    # 3. get_employee_by_id Match
    elif "employee id" in q or re.search(r"\bemp\d+\b", q):
        match = re.search(r"\bemp\d+\b", q)
        if match:
            tool_name = "get_employee_by_id"
            args = {"employee_id": match.group(0).upper()}

    # 4. get_all_employees Match
    elif q in ("all employees", "get all employees", "show all employees", "list all employees"):
        tool_name = "get_all_employees"

    # 5. search_employees Match
    elif q.startswith("search employee ") or q.startswith("search "):
        keyword = q.replace("search employee", "").replace("search", "").strip()
        if keyword:
            tool_name = "search_employees"
            args = {"keyword": keyword}

    # 6. get_employees_by_department Match
    elif "department employees" in q or "employees in" in q or "employees of" in q:
        # Extract department candidate
        dept_candidate = q.replace("department employees", "").replace("get employees by department", "").strip()
        # Handle "employees in [dept] department" or similar
        match = re.search(r"employees (?:in|of|for|belonging to)\s+(?:the\s+)?([\w\s]+?)(?:\s+department)?$", q)
        if match:
            dept_candidate = match.group(1).strip()
        if dept_candidate:
            tool_name = "get_employees_by_department"
            args = {"department": dept_candidate.title()}

    # 7. hr_insights Match
    elif any(k in q for k in ("utilization", "ftr", "rework", "top performer", "bottom performer", "performance summary")):
        tool_name = "hr_insights"
        args = {"question": question}

    # 8. connect_google_sheet Match
    elif "google sheet" in q or "connect google sheet" in q or "connect sheet" in q or "sync sheet" in q or "import sheet" in q:
        # Extract URL
        url_match = re.search(r'(https?://[^\s]+)', question)
        sheet_url = url_match.group(1) if url_match else ""
        tool_name = "connect_google_sheet"
        args = {"sheet_url": sheet_url}

    # 9. load_timesheets Match
    elif "upload timesheet" in q or "load timesheet" in q or "load timesheets" in q:
        tool_name = "load_timesheets"

    # 10. Smart SQL Fast Path Match
    elif any(q.startswith(p) for p in ("show all data from", "display all data from", "read table", "select * from", "display ", "show ", "read ")):
        # Try to find a table alias in the query
        canonical_table = None
        for alias in sorted(TABLE_ALIAS_MAP.keys(), key=len, reverse=True):
            if alias in q:
                canonical_table = resolve_table_name(alias)
                break
        
        if canonical_table:
            sql_to_execute = f"SELECT * FROM {canonical_table} LIMIT 100;"
            tool_name = "execute_sql"
            args = {"sql": sql_to_execute}

    # 11. Database Query Templates Match
    if not tool_name and not sql_to_execute:
        # Template: Average Salary
        if "average salary" in q or "mean salary" in q or "avg salary" in q:
            sql_to_execute = "SELECT AVG(annual_salary_inr) as avg_salary FROM employees;"
            tool_name = "execute_sql"
            args = {"sql": sql_to_execute}

        # Template: Group By Department
        elif "by department" in q or "group by department" in q:
            # Detect table
            table_candidate = "employees"
            for t_candidate in TABLE_ALIAS_MAP.keys():
                if t_candidate in q and t_candidate != "employee":
                    table_candidate = t_candidate
                    break
            canonical_table = resolve_table_name(table_candidate) or "employees"
            sql_to_execute = f"SELECT department, COUNT(*) as count FROM {canonical_table} GROUP BY department;"
            tool_name = "execute_sql"
            args = {"sql": sql_to_execute}

        # Template: Count Rows
        elif q.startswith("count ") or q.startswith("total ") or "how many" in q:
            # Check table candidate
            table_candidate = None
            for alias in TABLE_ALIAS_MAP.keys():
                if alias in q:
                    table_candidate = alias
                    break
            if table_candidate:
                canonical_table = resolve_table_name(table_candidate)
                sql_to_execute = f"SELECT COUNT(*) as total FROM {canonical_table};"
                tool_name = "execute_sql"
                args = {"sql": sql_to_execute}

        # Template: Distinct Values
        elif q.startswith("distinct ") or q.startswith("unique "):
            match = re.match(r"^(?:distinct|unique)\s+(\w+)\s+(?:in|from|of)?\s*(?:table\s+)?(\w+)$", q)
            if match:
                col = match.group(1)
                canonical_table = resolve_table_name(match.group(2))
                if canonical_table:
                    sql_to_execute = f"SELECT DISTINCT {col} FROM {canonical_table};"
                    tool_name = "execute_sql"
                    args = {"sql": sql_to_execute}

        # Template: Top N / Bottom N / Latest N
        elif q.startswith("top ") or q.startswith("best ") or q.startswith("highest ") or q.startswith("bottom ") or q.startswith("worst ") or q.startswith("lowest ") or q.startswith("latest ") or q.startswith("recent "):
            limit_val = 5
            limit_match = re.search(r"\b(\d+)\b", q)
            if limit_match:
                limit_val = int(limit_match.group(1))

            table_candidate = "employees"
            for alias in TABLE_ALIAS_MAP.keys():
                if alias in q and alias != "employee":
                    table_candidate = alias
                    break
            canonical_table = resolve_table_name(table_candidate) or "employees"

            # Determine order column
            col = "created_at"
            if canonical_table == "employees":
                if "salary" in q:
                    col = "annual_salary_inr"
                else:
                    col = "date_of_joining"
            elif canonical_table == "employee_kpis":
                col = "achievement_percentage"
            elif canonical_table == "timesheets":
                if "hours" in q:
                    col = "actual_hours"
                else:
                    col = "completion_date"

            order = "DESC"
            if any(k in q for k in ("bottom", "worst", "lowest")):
                order = "ASC"

            sql_to_execute = f"SELECT * FROM {canonical_table} ORDER BY {col} {order} LIMIT {limit_val};"
            tool_name = "execute_sql"
            args = {"sql": sql_to_execute}

    # Fallback to single ask_database call if no query routing matched and query seems database-focused
    if not tool_name:
        logger.info(f"[QueryRouter] Unmatched query fallback to Groq ask_database: '{question}'")
        tool_name = "ask_database"
        args = {"question": question}
        database_query = True

    # --- Execute Matched Tool ---
    router_time = time.perf_counter() - start_time
    tool_start = time.perf_counter()

    try:
        if tool_name == "list_tables":
            res = await list_tables()
            table_names = []
            for t in res if isinstance(res, list) else []:
                name = t.get("name") if isinstance(t, dict) else t
                if name:
                    table_names.append(name)
            answer = "### Database Tables\nHere are the available tables in the database:\n\n" + "\n".join([f"- **{name}**" for name in table_names])

        elif tool_name == "describe_table":
            res = await describe_table(**args)
            answer = f"### Table Schema: {args['table_name']}\n" + format_as_markdown_table(res)

        elif tool_name == "get_employee_by_id":
            res = await get_employee_by_id(**args)
            if not res:
                answer = f"No employee found with ID: **{args['employee_id']}**."
            elif isinstance(res, dict) and "error" in res:
                answer = f"Failed to retrieve employee: {res['error']}"
            else:
                headers = "| Field | Value |"
                sep = "|---|---|"
                rows = [f"| **{k.replace('_', ' ').title()}** | {v} |" for k, v in res.items()]
                answer = f"### Employee Details for {args['employee_id']}\n\n" + "\n".join([headers, sep] + rows)

        elif tool_name == "get_all_employees":
            res = await get_all_employees()
            answer = "### Employees Listing\n" + format_as_markdown_table(res)

        elif tool_name == "search_employees":
            res = await search_employees(**args)
            answer = f"### Employee Search Results for '{args['keyword']}'\n" + format_as_markdown_table(res)

        elif tool_name == "get_employees_by_department":
            res = await get_employees_by_department(**args)
            answer = f"### Employees in {args['department']} Department\n" + format_as_markdown_table(res)

        elif tool_name == "hr_insights":
            res = await hr_insights(**args)
            answer = res

        elif tool_name == "connect_google_sheet":
            res = await connect_google_sheet(**args)
            answer = res

        elif tool_name == "load_timesheets":
            res = await load_timesheets()
            answer = res

        elif tool_name == "execute_sql":
            res = await execute_sql(**args)
            sql = args["sql"]
            answer = f"### Query Result: {sql}\n" + format_as_markdown_table(res)

        elif tool_name == "ask_database":
            res = await ask_database(**args)
            answer = res

        else:
            raise ValueError(f"Unknown matched tool: {tool_name}")

    except Exception as e:
        logger.error(f"[QueryRouter] Execution error in tool {tool_name}: {e}")
        answer = f"Failed to execute tool {tool_name}: {str(e)}"
        res = {"error": str(e), "success": False}

    tool_time = time.perf_counter() - tool_start
    database_time = tool_time if tool_name in ("list_tables", "describe_table", "execute_sql", "ask_database", "get_employee_by_id", "get_all_employees", "get_employees_by_department", "search_employees") else 0.0
    total_time = time.perf_counter() - start_time

    # Instrumentation Logging
    logger.info("=" * 60)
    logger.info("PERFORMANCE METRICS SUMMARY (FAST PATH INTENT ROUTED)")
    logger.info(f"  Router Time:         {router_time * 1000:.2f} ms")
    logger.info(f"  Tool Execution Time: {tool_time * 1000:.2f} ms")
    logger.info(f"  Database Time:       {database_time * 1000:.2f} ms")
    logger.info(f"  Total Request Time:  {total_time * 1000:.2f} ms")
    logger.info("=" * 60)

    steps = [{
        "node": "Fast Path Router",
        "message": f"Bypassed LangGraph/Groq: Executed '{tool_name}' directly in {total_time:.3f}s.",
        "timestamp": datetime.now().isoformat()
    }]

    return {
        "answer": answer,
        "steps": steps,
        "tools_used": [tool_name],
        "steps_count": 1
    }
