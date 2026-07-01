import re
from src.core.logging.logger import logger
from src.services.ai.business_dictionary import COLUMN_ALIASES, resolve_aliases

TABLE_TOPICS = {
    "employees": {
        "employee", "staff", "hire", "salary", "department", "dept",
        "headcount", "joining", "location", "status", "active",
        "inactive", "gender", "role", "manager", "email", "phone",
        "first_name", "last_name", "annual_salary", "achievement_percentage"
    },
    "projects": {
        "project", "projects", "hours", "hours_worked", "working",
        "project_name", "project_id", "project_status", "contributed",
        "status", "team", "assignment", "assigned", "work", "contributor"
    },
    "timesheet_summary": {
        "timesheet", "hours", "utilization", "workload", "rework_tasks",
        "total_tasks", "month", "productivity", "logged", "average", "avg"
    },
    "task_logs": {
        "task", "rework", "category", "effort", "confidence",
        "eta", "breakdown", "completion", "actual_hours", "developer", "lead"
    },
    "audit_logs": {
        "audit", "change", "event", "history", "action",
        "who", "modified", "actor"
    },
    "import_history": {
        "import", "sync", "loaded", "csv", "source", "batch"
    },
    "imported_datasets": {
        "dataset", "table", "import", "source", "file"
    },
    "timesheets": {
        "timesheet", "hours", "utilization", "workload", "rework", "task",
        "eta", "actual_hours", "ftr", "rework_flag", "ftr_flag", "month", "year",
        "task_name", "eta_hours", "task_status", "completion_date",
        "achievement", "achievement_percentage", "performance", "performer", "ranking",
        "kpi", "trend", "distribution"
    }
}

# ---------------------------------------------------------------------------
# Terms that signal a multi-table / analytical query.
# When ANY of these appear, we return ALL available tables so the LLM has
# full visibility and can construct JOIN / GROUP BY queries correctly.
# ---------------------------------------------------------------------------
_COMPLEX_QUERY_TERMS = frozenset([
    "and the", "working on", "joined", "join",
    "project", "projects", "hours worked", "hours_worked",
    "contributed", "most", "highest", "lowest", "least",
    "across", "between", "sum", "total hours", "average hours",
    "per department", "group by", "aggregate", "contributors",
])


class TableSelector:
    def __init__(self, schema_builder=None):
        self.schema_builder = schema_builder

    def _is_complex_query(self, question: str) -> bool:
        """Returns True if the question likely requires multi-table reasoning."""
        q = question.lower()
        return any(term in q for term in _COMPLEX_QUERY_TERMS)

    async def select_tables(self, question: str, min_score: float = 0.0) -> list[str]:
        """
        Dynamically extracts tokens from the question and matches against table names
        and column names found in the database. Falls back to hardcoded TABLE_TOPICS if 
        schema_builder is not available.
        """
        enriched_question = resolve_aliases(question)
        cleaned = re.sub(r'[^a-z0-9_\s]', ' ', enriched_question.lower())
        tokens = set(cleaned.split())

        # If schema_builder is available, fetch full schema and build keywords dynamically
        if self.schema_builder:
            try:
                full_schema = await self.schema_builder.get_full_schema()
                if full_schema:
                    # For complex multi-table queries, return ALL tables so the LLM
                    # has full schema visibility to construct JOINs correctly.
                    if self._is_complex_query(question):
                        all_tables = list(full_schema.keys())
                        logger.info(
                            f"[TableSelector] Complex query detected. "
                            f"Returning ALL tables: {all_tables}"
                        )
                        return all_tables

                    scores = {}
                    for table_name, columns in full_schema.items():
                        table_lower = table_name.lower()
                        keywords = {table_lower}
                        
                        # Singular / plural variants
                        if table_lower.endswith("s"):
                            keywords.add(table_lower[:-1])
                        else:
                            keywords.add(table_lower + "s")
                            
                        # Split by underscore
                        keywords.update(table_lower.split("_"))
                        
                        # Column names
                        for col in columns:
                            col_name = col.get("name", "").lower()
                            keywords.add(col_name)
                            keywords.update(col_name.split("_"))
                            
                        # Calculate overlap
                        overlap = tokens & keywords
                        score = len(overlap)
                        if score > min_score:
                            scores[table_name] = score
                            
                    if not scores:
                        logger.info("No dynamically discovered table keywords matched. Scoping to all tables as fallback.")
                        return list(full_schema.keys())
                        
                    selected = sorted(scores, key=scores.get, reverse=True)
                    logger.info(f"Selected tables for query: {selected} (Scores: {scores})")
                    return selected
            except Exception as e:
                logger.error(f"Failed to fetch dynamic schema in table selector: {e}. Falling back to static topics.")

        # For complex queries in static fallback, return all known topics
        if self._is_complex_query(question):
            all_static = list(TABLE_TOPICS.keys())
            logger.info(
                f"[TableSelector] Complex query (static fallback). "
                f"Returning ALL static topics: {all_static}"
            )
            return all_static

        # Fallback to static topics
        scores = {}
        for table, keywords in TABLE_TOPICS.items():
            overlap = tokens & keywords
            score = len(overlap)
            if score > min_score:
                scores[table] = score

        if not scores:
            logger.info("No table topic keywords matched. Scoping to all tables as fallback.")
            return list(TABLE_TOPICS.keys())

        selected = sorted(scores, key=scores.get, reverse=True)
        logger.info(f"Selected tables for query: {selected} (Scores: {scores})")
        return selected
