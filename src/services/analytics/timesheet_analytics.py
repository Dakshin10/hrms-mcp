from src.core.logging.logger import logger
from src.services.query.query_service import query_service as default_query_service


class TimesheetAnalytics:
    def __init__(self, query_service=None):
        self.query_service = query_service or default_query_service

    async def eta_adherence_by_department(self, year=None, month=None) -> list[dict]:
        try:
            conditions = []
            params = []
            if year is not None:
                conditions.append("year = ?")
                params.append(year)
            if month is not None:
                conditions.append("month = ?")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"""
                SELECT department,
                       CASE WHEN AVG(eta_hours / NULLIF(actual_hours, 0)) * 100 > 100 
                            THEN 100 
                            ELSE AVG(eta_hours / NULLIF(actual_hours, 0)) * 100 
                       END AS eta_adherence
                FROM timesheets
                {where_clause}
                GROUP BY department
                ORDER BY eta_adherence DESC
            """
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"TimesheetAnalytics eta_adherence_by_department failed: {e}")
            return []

    async def ftr_rate_by_department(self, year=None, month=None) -> list[dict]:
        try:
            conditions = []
            params = []
            if year is not None:
                conditions.append("year = ?")
                params.append(year)
            if month is not None:
                conditions.append("month = ?")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"""
                SELECT department, AVG(ftr_flag) * 100 AS ftr_rate
                FROM timesheets
                {where_clause}
                GROUP BY department
                ORDER BY ftr_rate DESC
            """
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"TimesheetAnalytics ftr_rate_by_department failed: {e}")
            return []

    async def employees_missing_eta(self, threshold=80, year=None, month=None) -> list[dict]:
        try:
            conditions = []
            params = []
            if year is not None:
                conditions.append("year = ?")
                params.append(year)
            if month is not None:
                conditions.append("month = ?")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"""
                SELECT employee_id, employee_name, department,
                       CASE WHEN AVG(eta_hours / NULLIF(actual_hours, 0)) * 100 > 100 
                            THEN 100 
                            ELSE AVG(eta_hours / NULLIF(actual_hours, 0)) * 100 
                       END AS avg_eta_adherence
                FROM timesheets
                {where_clause}
                GROUP BY employee_id, employee_name, department
                HAVING avg_eta_adherence < ?
                ORDER BY avg_eta_adherence ASC
            """
            params.append(threshold)
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"TimesheetAnalytics employees_missing_eta failed: {e}")
            return []

    async def rework_report(self, year=None, month=None) -> list[dict]:
        try:
            conditions = []
            params = []
            if year is not None:
                conditions.append("year = ?")
                params.append(year)
            if month is not None:
                conditions.append("month = ?")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"""
                SELECT employee_id, employee_name, department,
                       SUM(rework_flag) AS rework_count,
                       AVG(rework_flag) * 100 AS rework_rate
                FROM timesheets
                {where_clause}
                GROUP BY employee_id, employee_name, department
                ORDER BY rework_rate DESC
            """
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"TimesheetAnalytics rework_report failed: {e}")
            return []

    async def utilization_by_employee(self, available_hours=160, year=None, month=None) -> list[dict]:
        try:
            conditions = []
            params = [available_hours]
            if year is not None:
                conditions.append("year = ?")
                params.append(year)
            if month is not None:
                conditions.append("month = ?")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"""
                SELECT employee_id, employee_name,
                       SUM(actual_hours) / ? * 100 AS utilization
                FROM timesheets
                {where_clause}
                GROUP BY employee_id, employee_name
                ORDER BY utilization DESC
            """
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"TimesheetAnalytics utilization_by_employee failed: {e}")
            return []
