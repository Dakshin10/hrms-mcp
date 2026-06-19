import re
from src.services.analytics.kpi_analytics import KPIAnalytics
from src.services.analytics.timesheet_analytics import TimesheetAnalytics
from src.services.analytics.employee_analytics import EmployeeAnalytics
from src.services.ai.answer_generator import generate_answer
from src.services.query.query_service import query_service
from src.core.logging.logger import logger


ROUTE_SCORES = {
    "top_performers": {
        "keywords": ["top", "best", "highest", "star", "performer", "leading"],
        "method": "kpi.top_performers"
    },
    "bottom_performers": {
        "keywords": ["bottom", "low", "worst", "struggling", "underperform", "below"],
        "method": "kpi.bottom_performers"
    },
    "attention": {
        "keywords": ["attention", "risk", "flag", "help", "needs", "concern", "problem"],
        "method": "employee.employees_needing_attention"
    },
    "department_kpi": {
        "keywords": ["department", "team", "group", "division", "which dept", "dept rank"],
        "method": "kpi.department_kpi_ranking"
    },
    "eta": {
        "keywords": ["eta", "deadline", "late", "missed", "on time", "delay", "overdue"],
        "method": "timesheet.employees_missing_eta"
    },
    "ftr": {
        "keywords": ["ftr", "rework", "first time", "quality", "redo", "correction"],
        "method": "timesheet.ftr_rate_by_department"
    },
    "utilization": {
        "keywords": ["utilization", "billable", "hours", "capacity", "workload"],
        "method": "timesheet.utilization_by_employee"
    },
}


class HRInsightsHandler:
    def __init__(self):
        self.kpi = KPIAnalytics(query_service)
        self.timesheet = TimesheetAnalytics(query_service)
        self.employee = EmployeeAnalytics(query_service)

    async def handle(self, question: str) -> str:
        q_lower = question.lower()

        # Parse year and month if present in the question
        year = None
        month = None

        year_match = re.search(r"\b(202\d)\b", q_lower)
        if year_match:
            year = int(year_match.group(1))

        months_map = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12
        }

        for m_name, m_val in months_map.items():
            if re.search(rf"\b{m_name}\b", q_lower):
                month = m_val
                break

        # Dynamic scoring router
        scores = {}
        for route, config in ROUTE_SCORES.items():
            score = 0
            for keyword in config["keywords"]:
                if keyword in q_lower:
                    score += 1
            scores[route] = score

        max_score = max(scores.values()) if scores else 0

        # Log selection and score as a metric
        logger.info(f"HRInsights Route Scores: {scores} (Max: {max_score})")

        if max_score == 0:
            # Fall through to ask_database() as before
            from src.services.text_to_sql import ask
            logger.info("No route matched. Falling back to ask_database().")
            res = await ask(question)
            return res.get("answer", "")

        # Get top routes
        top_routes = [r for r, s in scores.items() if s == max_score]

        async def call_method(method_path: str) -> list[dict]:
            parts = method_path.split(".")
            module_obj = getattr(self, parts[0])
            func = getattr(module_obj, parts[1])
            
            kwargs = {
                "year": year,
                "month": month
            }
            if parts[1] == "top_performers":
                kwargs["limit"] = 10
            elif parts[1] == "bottom_performers":
                kwargs["threshold"] = 70
                
            return await func(**kwargs)

        results = []
        sql_used = ""
        
        if len(top_routes) == 1:
            route = top_routes[0]
            sql_used = ROUTE_SCORES[route]["method"]
            results = await call_method(sql_used)
            logger.info(f"HR insights routed to {route} with score {max_score}", extra={"metric": {"route": route, "score": max_score}})
        else:
            # Tie: run both/all, merge results, pass to answer_generator
            logger.info(f"HR insights tie detected: {top_routes} with score {max_score}", extra={"metric": {"routes": top_routes, "score": max_score}})
            sql_used_list = []
            for route in top_routes:
                method_path = ROUTE_SCORES[route]["method"]
                sql_used_list.append(method_path)
                res_list = await call_method(method_path)
                if isinstance(res_list, list):
                    results.extend(res_list)
            sql_used = " + ".join(sql_used_list)

        # Generate NL Answer based on query results
        answer = await generate_answer(question, sql_used, results)
        return answer
