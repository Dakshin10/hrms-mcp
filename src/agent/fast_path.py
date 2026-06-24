import re
import json
import time
from datetime import datetime
from src.core.logging.logger import logger
from src.tools.db_tools import list_tables, describe_table, execute_sql, cache_stats
from src.tools.employee_tools import get_all_employees, get_employee_by_id, get_employees_by_department, search_employees

def format_as_markdown_table(rows: list) -> str:
    if not rows:
        return "No records found."
    if isinstance(rows, dict) and "error" in rows:
        return f"Error: {rows['error']}"
    if not isinstance(rows, list):
        return str(rows)
    if len(rows) == 0:
        return "No records found."
        
    headers = list(rows[0].keys())
    header_row = "| " + " | ".join([h.replace("_", " ").title() for h in headers]) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    
    data_rows = []
    for row in rows:
        vals = []
        for h in headers:
            val = row.get(h)
            if val is None:
                val = ""
            vals.append(str(val))
        data_rows.append("| " + " | ".join(vals) + " |")
        
    return "\n".join([header_row, separator_row] + data_rows)

async def fast_path_router(question: str) -> dict | None:
    """
    Analyzes the query and routes it directly to a tool if it matches simple patterns.
    Returns a result dict if handled, or None if it should go through the LangGraph Agent.
    """
    q = question.strip().lower()
    
    # Remove trailing question mark or semicolon
    if q.endswith("?") or q.endswith(";"):
        q = q[:-1].strip()
        
    start_time = time.perf_counter()
    
    # 1. list_tables Match
    list_tables_pattern = r"^(show|list|get)\s+(all\s+)?(available\s+)?tables$"
    if re.match(list_tables_pattern, q) or q == "what tables are available":
        logger.info("[Fast Path] Intercepted list_tables request")
        tables = await list_tables()
        dur = time.perf_counter() - start_time
        
        if isinstance(tables, dict) and "error" in tables:
            answer = f"Failed to list tables: {tables['error']}"
        else:
            table_names = []
            for t in tables if isinstance(tables, list) else []:
                if isinstance(t, dict) and "name" in t:
                    table_names.append(t["name"])
                elif isinstance(t, str):
                    table_names.append(t)
            answer = "### Database Tables\nHere are the available tables in the database:\n\n" + "\n".join([f"- **{name}**" for name in table_names])
            
        return {
            "answer": answer,
            "steps": [{
                "node": "Fast Path Router",
                "message": f"Bypassed LangGraph/Groq: Executed 'list_tables' directly in {dur:.3f}s.",
                "timestamp": datetime.now().isoformat()
            }],
            "tools_used": ["list_tables"],
            "timings": {"router": dur, "tool": dur, "database": dur, "total": dur}
        }
        
    # 2. cache_stats Match
    cache_stats_pattern = r"^(show|get|list)?\s*cache\s+stats(tics)?$"
    if re.match(cache_stats_pattern, q):
        logger.info("[Fast Path] Intercepted cache_stats request")
        stats = await cache_stats()
        dur = time.perf_counter() - start_time
        
        return {
            "answer": f"### Query Cache Statistics\n\n{stats}",
            "steps": [{
                "node": "Fast Path Router",
                "message": f"Bypassed LangGraph/Groq: Executed 'cache_stats' directly in {dur:.3f}s.",
                "timestamp": datetime.now().isoformat()
            }],
            "tools_used": ["cache_stats"],
            "timings": {"router": dur, "tool": dur, "total": dur}
        }

    # 3. get_employee_by_id Match
    emp_by_id_pattern = r"^(find|get|show|lookup)\s+(employee\s+)?(emp\d+)$"
    match = re.match(emp_by_id_pattern, q)
    if match:
        emp_id = match.group(3).upper()
        logger.info(f"[Fast Path] Intercepted get_employee_by_id request for: {emp_id}")
        employee = await get_employee_by_id(emp_id)
        dur = time.perf_counter() - start_time
        
        if not employee:
            answer = f"No employee found with ID: **{emp_id}**."
        elif isinstance(employee, dict) and "error" in employee:
            answer = f"Failed to retrieve employee: {employee['error']}"
        else:
            # Format single dictionary as markdown table
            headers = "| Field | Value |"
            sep = "|---|---|"
            rows = [f"| **{k.replace('_', ' ').title()}** | {v} |" for k, v in employee.items()]
            answer = f"### Employee Details for {emp_id}\n\n" + "\n".join([headers, sep] + rows)
            
        return {
            "answer": answer,
            "steps": [{
                "node": "Fast Path Router",
                "message": f"Bypassed LangGraph/Groq: Executed 'get_employee_by_id' for {emp_id} in {dur:.3f}s.",
                "timestamp": datetime.now().isoformat()
            }],
            "tools_used": ["get_employee_by_id"],
            "timings": {"router": dur, "tool": dur, "database": dur, "total": dur}
        }

    # 4. get_all_employees Match
    if q in ("get all employees", "show all employees", "list all employees", "all employees"):
        logger.info("[Fast Path] Intercepted get_all_employees request")
        employees = await get_all_employees()
        dur = time.perf_counter() - start_time
        
        answer = "### Employees Listing\n" + format_as_markdown_table(employees)
        return {
            "answer": answer,
            "steps": [{
                "node": "Fast Path Router",
                "message": f"Bypassed LangGraph/Groq: Executed 'get_all_employees' directly in {dur:.3f}s.",
                "timestamp": datetime.now().isoformat()
            }],
            "tools_used": ["get_all_employees"],
            "timings": {"router": dur, "tool": dur, "database": dur, "total": dur}
        }

    # Helper for known tables lookup to prevent greedy regex intercepting non-table queries
    tables = await list_tables()
    known_tables = []
    if isinstance(tables, list):
        for t in tables:
            if isinstance(t, dict) and "name" in t:
                known_tables.append(t["name"].lower())
            elif isinstance(t, str):
                known_tables.append(t.lower())

    # 5. describe_table Match
    describe_pattern = r"^(describe|schema|info|columns|details\s+of)\s+(table\s+)?(\w+)$"
    match = re.match(describe_pattern, q)
    if match:
        table_name = match.group(3)
        if table_name.lower() in known_tables:
            logger.info(f"[Fast Path] Intercepted describe_table request for: {table_name}")
            schema = await describe_table(table_name)
            dur = time.perf_counter() - start_time
            
            answer = f"### Table Schema: {table_name}\n" + format_as_markdown_table(schema)
            return {
                "answer": answer,
                "steps": [{
                    "node": "Fast Path Router",
                    "message": f"Bypassed LangGraph/Groq: Executed 'describe_table' for {table_name} in {dur:.3f}s.",
                    "timestamp": datetime.now().isoformat()
                }],
                "tools_used": ["describe_table"],
                "timings": {"router": dur, "tool": dur, "database": dur, "total": dur}
            }

    # 6. get_employees_by_department Match
    dept_pattern1 = r"^(get|show|list)\s+employees\s+(in|of|for|belonging\s+to)\s+department\s+(.+)$"
    dept_pattern2 = r"^(get|show|list)\s+employees\s+(in|of|for|belonging\s+to)\s+(.+)\s+department$"
    dept_pattern3 = r"^department\s+(.+)$"
    
    match1 = re.match(dept_pattern1, q)
    match2 = re.match(dept_pattern2, q)
    match3 = re.match(dept_pattern3, q)
    
    dept_name = None
    if match1:
        dept_name = match1.group(3)
    elif match2:
        dept_name = match2.group(3)
    elif match3:
        dept_name = match3.group(1)
        
    if dept_name:
        # Check that it doesn't look like an general query
        dept_name_clean = dept_name.strip().title()
        logger.info(f"[Fast Path] Intercepted get_employees_by_department request for: {dept_name_clean}")
        employees = await get_employees_by_department(dept_name_clean)
        dur = time.perf_counter() - start_time
        
        answer = f"### Employees in {dept_name_clean} Department\n" + format_as_markdown_table(employees)
        return {
            "answer": answer,
            "steps": [{
                "node": "Fast Path Router",
                "message": f"Bypassed LangGraph/Groq: Executed 'get_employees_by_department' for {dept_name_clean} in {dur:.3f}s.",
                "timestamp": datetime.now().isoformat()
            }],
            "tools_used": ["get_employees_by_department"],
            "timings": {"router": dur, "tool": dur, "database": dur, "total": dur}
        }

    # 7. search_employees Match
    search_pattern = r"^search\s+(employee(s)?\s+(for|by|matching|with)?\s+)?(.+)$"
    match = re.match(search_pattern, q)
    if match:
        keyword = match.group(4)
        logger.info(f"[Fast Path] Intercepted search_employees request for keyword: {keyword}")
        employees = await search_employees(keyword)
        dur = time.perf_counter() - start_time
        
        answer = f"### Employee Search Results for '{keyword}'\n" + format_as_markdown_table(employees)
        return {
            "answer": answer,
            "steps": [{
                "node": "Fast Path Router",
                "message": f"Bypassed LangGraph/Groq: Executed 'search_employees' for '{keyword}' in {dur:.3f}s.",
                "timestamp": datetime.now().isoformat()
            }],
            "tools_used": ["search_employees"],
            "timings": {"router": dur, "tool": dur, "database": dur, "total": dur}
        }

    # 8. Smart SQL Fast Path Match
    # Pattern: display all data from X, show all data from X, select * from X
    select_all_pattern1 = r"^(display|show|get|select|list)\s+all\s+(data|records|rows)?\s*(from|of)?\s*(table\s+)?(\w+)$"
    select_all_pattern2 = r"^select\s+\*\s+from\s+(\w+)\s*(limit\s+\d+)?$"
    
    match1 = re.match(select_all_pattern1, q)
    match2 = re.match(select_all_pattern2, q)
    
    target_table = None
    limit_val = 100
    
    if match1:
        target_table = match1.group(5)
    elif match2:
        target_table = match2.group(1)
        if match2.group(2):
            try:
                limit_val = int(re.search(r"\d+", match2.group(2)).group())
            except:
                pass
                
    if target_table and target_table.lower() in known_tables:
        # Match table name casing exactly as it exists in known_tables if possible, or use target_table
        tables_full = await list_tables()
        db_table = target_table
        if isinstance(tables_full, list):
            for t in tables_full:
                name = t.get("name") if isinstance(t, dict) else t
                if name and name.lower() == target_table.lower():
                    db_table = name
                    break
        sql = f"SELECT * FROM {db_table} LIMIT {limit_val};"
        logger.info(f"[Fast Path] Intercepted Smart SQL Fast Path for table: {db_table} -> {sql}")
        
        results = await execute_sql(sql)
        dur = time.perf_counter() - start_time
        
        answer = f"### Query Result: {sql}\n" + format_as_markdown_table(results)
        return {
            "answer": answer,
            "steps": [{
                "node": "Fast Path Router",
                "message": f"Bypassed LangGraph/Groq: Executed Smart SQL query directly in {dur:.3f}s.",
                "timestamp": datetime.now().isoformat()
            }],
            "tools_used": ["execute_sql"],
            "timings": {"router": dur, "tool": dur, "database": dur, "total": dur}
        }
        
    return None
