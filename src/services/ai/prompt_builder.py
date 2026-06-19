from src.services.ai.business_dictionary import get_term_definitions, resolve_aliases

SYSTEM_PROMPT = """You are an expert SQL analyst for an HR Management System (HRMS) using Cloudflare D1 (SQLite-compatible).

STRICT RULES:
1. Return ONLY raw SQL. No markdown, no explanation, no code fences.
2. Generate ONLY SELECT or WITH (CTE) statements.
3. NEVER use columns or tables not explicitly listed in the provided schema.
4. NEVER hallucinate column names. If a column does not appear in the schema, it does not exist.
5. For KPI/performance questions:
   - Utilization is in `timesheet_summary.utilization_percentage`
   - Task efficiency is in `task_logs.actual_hours` vs `task_logs.eta`
   - Rework rate is `timesheet_summary.rework_tasks / timesheet_summary.total_tasks`
6. Always qualify column names with table aliases to prevent ambiguity.
7. Always use meaningful aliases: COUNT(*) AS employee_count, NOT COUNT(*).
8. If a question cannot be answered from the provided schema, return exactly:
   SELECT 'CANNOT_ANSWER' AS error, 'Reason: [brief reason]' AS reason;
9. For employee lookups, always join on employee_id — NEVER join on employee_name (not a primary key).
10. LIMIT results to 100 rows unless the question explicitly asks for all records.
11. Even if an employee, department, or month mentioned in the question does not exist or is not found in the database, always generate the correct SELECT query on the appropriate tables (e.g. timesheets, employees) to let the database return 0 rows naturally, rather than returning CANNOT_ANSWER or hardcoding a message.
"""


FEW_SHOT_EXAMPLES = """--- SQL Examples ---
Q: How many employees are there?
SQL: SELECT COUNT(*) AS employee_count FROM employees

Q: Who are the top 5 KPI performers?
SQL: SELECT employee_id, employee_name, ROUND(AVG(ftr_flag) * 100, 2) AS achievement_percentage FROM timesheets GROUP BY employee_id, employee_name ORDER BY achievement_percentage DESC LIMIT 5

Q: Which department has the best FTR?
SQL: SELECT department, ROUND(AVG(ftr_flag) * 100, 2) AS ftr_rate FROM timesheets GROUP BY department ORDER BY ftr_rate DESC

Q: Show employees missing ETA targets
SQL: SELECT employee_id, employee_name, ROUND(AVG(CAST(eta_hours AS FLOAT) / NULLIF(actual_hours, 0)) * 100, 2) AS eta_adherence FROM timesheets GROUP BY employee_id, employee_name HAVING eta_adherence < 80 ORDER BY eta_adherence ASC

Q: Which employees have high rework?
SQL: SELECT employee_id, employee_name, ROUND(AVG(rework_flag) * 100, 2) AS rework_rate FROM timesheets GROUP BY employee_id, employee_name HAVING rework_rate > 20 ORDER BY rework_rate DESC

Q: Show KPI trend for EMP0001
SQL: SELECT year, month, ROUND(AVG(ftr_flag) * 100, 2) AS achievement_percentage FROM timesheets WHERE employee_id = 'EMP0001' GROUP BY year, month ORDER BY year ASC, month ASC
--- End Examples ---"""


class PromptBuilder:
    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(self, question: str, schema_str: str) -> str:
        enriched_question = resolve_aliases(question)
        definitions = get_term_definitions(question)
        
        definitions_section = f"\n{definitions}" if definitions else ""

        return f"""## Available Schema (ONLY use these tables and columns):

{schema_str}
{definitions_section}

{FEW_SHOT_EXAMPLES}

## User Question:
{enriched_question}

## SQL Query:
"""

