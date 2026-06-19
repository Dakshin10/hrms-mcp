from src.services.metadata.metadata_service import metadata_service
from src.services.query.query_service import query_service
from src.core.logging.logger import logger

FAST_PATH_RULES = [
    {
        "patterns": ["list tables", "show tables", "what tables"],
        "handler": "list_tables"
    },
    {
        "patterns": ["count employees", "how many employees", "total employees", "number of employees", "count all employees", "employee count", "how many staff", "number of staff"],
        "handler": "count_employees"
    },
    {
        "patterns": ["count departments", "how many departments"],
        "handler": "count_departments"
    },
    {
        "patterns": ["show all departments", "list departments", "all departments"],
        "handler": "list_departments"
    },
    {
        "patterns": ["total tasks", "how many tasks", "count tasks"],
        "handler": "count_tasks"
    },
    {
        "patterns": ["list employees", "show all employees", "all employees"],
        "handler": "list_employees"
    },
    {
        "patterns": ["show all timesheets", "list timesheets"],
        "handler": "list_timesheets"
    },
]


class FastPathHandler:
    async def try_handle(self, question: str) -> dict | None:
        normalized = " ".join(question.lower().split()).strip().rstrip("?")

        # Security check: if question contains any DDL/DML mutation keywords, do not fast path
        import re
        blocked_words = {"delete", "drop", "update", "insert", "alter", "truncate"}
        words = set(re.findall(r'[a-z]+', normalized))
        if words & blocked_words:
            return None

        matched_handler = None
        for rule in FAST_PATH_RULES:
            if any(pattern in normalized for pattern in rule["patterns"]):
                matched_handler = rule["handler"]
                break

        if not matched_handler:
            return None

        logger.info(f"Fast path matched: {matched_handler} for question: '{question}'")
        try:
            handler_method = getattr(self, matched_handler)
            return await handler_method()
        except Exception as e:
            logger.error(f"Fast path handler {matched_handler} execution failed: {e}")
            return None

    async def list_tables(self) -> dict:
        tables = await metadata_service.get_tables()
        table_names = [t.get("name") for t in tables if t.get("name")]
        return {
            "generated_sql": "-- Fast Path Table Listing",
            "results": tables,
            "answer": f"The available tables in the system are: {', '.join(table_names)}.",
            "fast_path": True
        }

    async def count_employees(self) -> dict:
        sql = "SELECT COUNT(*) AS total_employees FROM employees"
        results = await query_service.execute_query(sql)
        count = results[0].get("total_employees", 0) if results else 0
        return {
            "generated_sql": sql,
            "results": results,
            "answer": f"There are currently {count} employees in the system.",
            "fast_path": True
        }

    async def count_departments(self) -> dict:
        sql = "SELECT COUNT(DISTINCT department) AS total_departments FROM employees"
        results = await query_service.execute_query(sql)
        count = results[0].get("total_departments", 0) if results else 0
        return {
            "generated_sql": sql,
            "results": results,
            "answer": f"There are currently {count} departments registered in the system.",
            "fast_path": True
        }

    async def list_departments(self) -> dict:
        sql = "SELECT DISTINCT department FROM timesheets WHERE department IS NOT NULL ORDER BY department"
        results = await query_service.execute_query(sql)
        depts = [r.get("department") for r in results if r.get("department")]
        
        if not depts:
            sql = "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL ORDER BY department"
            results = await query_service.execute_query(sql)
            depts = [r.get("department") for r in results if r.get("department")]
            
        if not depts:
            return {
                "generated_sql": sql,
                "results": [],
                "answer": "No department data found. Load timesheet data first using load_timesheets().",
                "fast_path": True
            }
            
        return {
            "generated_sql": sql,
            "results": results,
            "answer": f"The departments in the system are: {', '.join(depts)}.",
            "fast_path": True
        }

    async def count_tasks(self) -> dict:
        sql = "SELECT COUNT(*) AS task_count FROM timesheets"
        results = await query_service.execute_query(sql)
        count = results[0].get("task_count", 0) if results else 0
        return {
            "generated_sql": sql,
            "results": results,
            "answer": f"There are currently {count} tasks logged in the timesheets.",
            "fast_path": True
        }

    async def list_employees(self) -> dict:
        sql = "SELECT DISTINCT employee_id, employee_name, department FROM timesheets ORDER BY employee_name"
        results = await query_service.execute_query(sql)
        names = [f"{r.get('employee_name')} ({r.get('employee_id')})" for r in results if r.get('employee_name')]
        return {
            "generated_sql": sql,
            "results": results,
            "answer": f"The employees registered in timesheets are: {', '.join(names)}.",
            "fast_path": True
        }

    async def list_timesheets(self) -> dict:
        sql = "SELECT * FROM timesheets LIMIT 20"
        results = await query_service.execute_query(sql)
        return {
            "generated_sql": sql,
            "results": results,
            "answer": f"Here is a sample of the timesheet logs (showing {len(results)} records).",
            "fast_path": True
        }
