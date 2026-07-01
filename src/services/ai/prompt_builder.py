from src.services.ai.business_dictionary import get_term_definitions, resolve_aliases

SYSTEM_PROMPT = """You are a precise SQL analyst for a Cloudflare D1 (SQLite-compatible) database.

STRICT RULES:
1. Return ONLY raw SQL. No markdown, no explanation, no code fences, no backticks.
2. Generate ONLY SELECT or WITH (CTE) statements — never INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.
3. NEVER use columns or tables not explicitly listed in the provided schema section below.
4. NEVER hallucinate column names. If a column is not in the schema, it does not exist.
5. NEVER assume specific column names (e.g., do NOT assume 'first_name', 'last_name', 'email').
   Use ONLY the exact column names shown in the ## Available Schema section.
6. Always qualify column names with table aliases when joining multiple tables (e.g. e.employee_name, p.project_name).
7. Always use meaningful aliases for aggregates: SUM(p.hours_worked) AS total_hours, NOT SUM(p.hours_worked).
8. If a question cannot be answered from the schema, return exactly:
   SELECT 'CANNOT_ANSWER' AS error, 'Reason: [brief reason]' AS reason;
9. For joins, inspect the ## Relationships section and use the listed join columns.
10. LIMIT results to 100 rows unless the question explicitly asks for all records.
11. If the data might simply not exist, still generate the correct SQL — let D1 return 0 rows naturally.
12. Never output a fallback like 'SELECT * FROM employees LIMIT 100' for analytical questions.
    Always attempt to generate the correct JOIN/GROUP BY/aggregation query.
"""


FEW_SHOT_EXAMPLES = """--- SQL Examples (illustrative only — ALWAYS use actual schema columns) ---

Q: How many rows are in the employees table?
SQL: SELECT COUNT(*) AS employee_count FROM employees

Q: Show all employees with their departments
SQL: SELECT employee_id, employee_name, department FROM employees ORDER BY employee_name

Q: Show all employees and the projects they are working on
SQL: SELECT e.employee_name, p.project_name, p.project_status
     FROM employees e
     JOIN projects p ON e.employee_id = p.employee_id

Q: Show employee names, departments, project names, and hours worked
SQL: SELECT e.employee_name, e.department, p.project_name, p.hours_worked
     FROM employees e
     JOIN projects p ON e.employee_id = p.employee_id

Q: Which department has contributed the most project hours?
SQL: SELECT e.department, SUM(p.hours_worked) AS total_hours
     FROM employees e
     JOIN projects p ON e.employee_id = p.employee_id
     GROUP BY e.department
     ORDER BY total_hours DESC

Q: Which employee is working on the AI Analytics project?
SQL: SELECT e.employee_name, e.department, p.project_status
     FROM employees e
     JOIN projects p ON e.employee_id = p.employee_id
     WHERE p.project_name = 'AI Analytics'

Q: Show the top contributors across all projects
SQL: SELECT e.employee_name, SUM(p.hours_worked) AS total_hours
     FROM employees e
     JOIN projects p ON e.employee_id = p.employee_id
     GROUP BY e.employee_name
     ORDER BY total_hours DESC
     LIMIT 10

Q: Which department has the most employees?
SQL: SELECT department, COUNT(*) AS employee_count
     FROM employees
     GROUP BY department
     ORDER BY employee_count DESC

--- End Examples ---"""


class PromptBuilder:
    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_prompt(self, question: str, schema_str: str, relationships: list[str] = None) -> str:
        enriched_question = resolve_aliases(question)
        definitions = get_term_definitions(question)

        definitions_section = f"\n{definitions}" if definitions else ""
        relationships_section = ""
        if relationships:
            relationships_section = (
                "\n## Relationships / Join Candidates (MUST use these for JOINs):\n"
                + "\n".join(relationships)
                + "\n"
            )

        return f"""## Available Schema (ONLY use these exact tables and columns — no others):

{schema_str}
{definitions_section}
{relationships_section}

{FEW_SHOT_EXAMPLES}

## User Question:
{enriched_question}

## SQL Query:
"""

