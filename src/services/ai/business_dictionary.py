import re

BUSINESS_TERMS = {
    "ftr": "First Time Right (FTR): The percentage of tasks completed without requiring rework.",
    "eta": "Estimated Time of Arrival (ETA): The estimated number of hours to complete a task.",
    "achievement_percentage": "Achievement Percentage: The performance rating or achievement score of an employee.",
    "rework": "Rework: Tasks that failed initial checks and required corrections/revisions.",
    "utilization": "Utilization: The percentage of logged productive hours out of total available working hours.",
    "kpi_score": "KPI Score: Key Performance Indicator rating representing overall execution quality.",
    "task_completion_rate": "Task Completion Rate: The ratio of completed tasks to total assigned tasks.",
    "productivity": "Productivity: Evaluated output level of an employee or team.",
    "billable_hours": "Billable Hours: Productive hours directly chargeable to client projects.",
    "on_time_delivery": "On-Time Delivery (OTD): The percentage of tasks completed on or before the original ETA.",
    "overdue_tasks": "Overdue Tasks: Logged assignments that have exceeded their ETA but remain incomplete.",
    "department_performance": "Department Performance: The aggregated average achievement/KPI score of a department.",
    "employee_rating": "Employee Rating: Performance classification based on feedback, FTR, and execution metrics."
}

COLUMN_ALIASES = {
    "top performer": "achievement_percentage DESC",
    "needs attention": "achievement_percentage < 70",
    "missed deadline": "eta < 100",
    "rework rate": "ftr"
}


def get_term_definitions(question: str) -> str:
    """
    Scans the question for known domain terms and returns a formatted definition block.
    """
    matched_definitions = []
    q_lower = question.lower()

    for term, definition in BUSINESS_TERMS.items():
        # Match whole word boundary to prevent matching inside other words
        if re.search(rf"\b{term}\b", q_lower):
            matched_definitions.append(definition)

    if not matched_definitions:
        return ""

    definitions_block = "\n".join(f"- {d}" for d in matched_definitions)
    return f"--- Business Term Definitions ---\n{definitions_block}\n"


def resolve_aliases(question: str) -> str:
    """
    Replaces natural language phrases in the query with SQL-friendly hints.
    """
    enriched = question
    q_lower = question.lower()

    # Add generic KPI/performance hints
    if "kpi" in q_lower or "performance" in q_lower or "performer" in q_lower or "underperforming" in q_lower or "struggling" in q_lower:
        enriched += " (hint: achievement_percentage represents KPI/performance rating)"

    if "top performer" in q_lower or "top performers" in q_lower or "best performer" in q_lower or "best performers" in q_lower:
        enriched += " (hint: sort by achievement_percentage DESC)"
    if "needs attention" in q_lower or "at risk" in q_lower or "low kpi" in q_lower or "underperforming" in q_lower or "struggling" in q_lower or "bottom performer" in q_lower or "bottom performers" in q_lower or "kpi rating under 70" in q_lower:
        enriched += " (hint: achievement_percentage < 70)"
    if "missed deadline" in q_lower or "overdue" in q_lower or "missed deadlines" in q_lower or "miss deadline" in q_lower or "who has missed deadlines" in q_lower:
        enriched += " (hint: compute AVG(eta_hours / NULLIF(actual_hours, 0)) * 100 AS avg_eta_adherence and filter having avg_eta_adherence < 80)"
    if "rework rate" in q_lower or "rework percentage" in q_lower:
        enriched += " (hint: ftr)"
    if "rework report" in q_lower or "rework by employee" in q_lower:
        enriched += " (hint: compute SUM(rework_flag) AS rework_count, ROUND(AVG(rework_flag) * 100, 2) AS rework_rate)"
    if "kpi distribution" in q_lower or "distribution of kpi" in q_lower or "performance distribution" in q_lower:
        enriched += " (hint: compute bands as SUM(CASE WHEN achievement >= 0 AND achievement < 50 THEN 1 ELSE 0 END) AS band_0_50, SUM(CASE WHEN achievement >= 50 AND achievement < 70 THEN 1 ELSE 0 END) AS band_50_70, SUM(CASE WHEN achievement >= 70 AND achievement < 85 THEN 1 ELSE 0 END) AS band_70_85, SUM(CASE WHEN achievement >= 85 AND achievement <= 100 THEN 1 ELSE 0 END) AS band_85_100 from a CTE calculating AVG(ftr_flag) * 100 AS achievement grouped by employee_id)"
    if "ftr and rework percentage" in q_lower or "ftr and rework rate" in q_lower:
        enriched += " (hint: compute AVG(ftr_flag) * 100 AS ftr_rate, AVG(rework_flag) * 100 AS rework_rate)"
    if "utilization" in q_lower:
        enriched += " (hint: query from timesheets, calculating utilization as the percentage of actual_hours relative to available hours (default 160))"

    return enriched
