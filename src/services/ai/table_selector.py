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


class TableSelector:
    def select_tables(self, question: str, min_score: float = 0.0) -> list[str]:
        """
        Extract tokens from query and match against predefined keywords for tables.
        Returns a sorted list of relevant tables, or all tables as fallback.
        """
        # Resolve semantic aliases first
        enriched_question = resolve_aliases(question)

        cleaned = re.sub(r'[^a-z0-9_\s]', ' ', enriched_question.lower())
        tokens = set(cleaned.split())

        scores = {}
        for table, keywords in TABLE_TOPICS.items():
            overlap = tokens & keywords
            score = len(overlap)
            if score > min_score:
                scores[table] = score

        if not scores:
            logger.info("No table topic keywords matched. Scoping to all tables as fallback.")
            return list(TABLE_TOPICS.keys())

        # Sort tables by score in descending order
        selected = sorted(scores, key=scores.get, reverse=True)
        logger.info(f"Selected tables for query: {selected} (Scores: {scores})")
        return selected

