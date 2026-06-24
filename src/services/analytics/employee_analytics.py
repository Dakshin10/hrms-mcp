from src.core.logging.logger import logger
from src.services.database.query_service import query_service as default_query_service


class EmployeeAnalytics:
    def __init__(self, query_service=None):
        self.query_service = query_service or default_query_service

    async def employees_needing_attention(self, year=None, month=None) -> list[dict]:
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
                WITH employee_metrics AS (
                    SELECT employee_id, employee_name AS name, department,
                           AVG(ftr_flag) * 100 AS achievement,
                           AVG(ftr_flag) * 100 AS ftr_rate,
                           AVG(rework_flag) * 100 AS rework_rate
                    FROM timesheets
                    {where_clause}
                    GROUP BY employee_id, employee_name, department
                )
                SELECT employee_id, name, department, achievement, ftr_rate, rework_rate,
                       CASE 
                           WHEN achievement < 70 THEN 'Low KPI'
                           WHEN rework_rate > 20 THEN 'High Rework'
                           WHEN ftr_rate < 70 THEN 'Low FTR'
                           ELSE 'Needs Attention'
                       END AS reason
                FROM employee_metrics
                WHERE achievement < 70 OR ftr_rate < 70 OR rework_rate > 20
            """
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"EmployeeAnalytics employees_needing_attention failed: {e}")
            return []

    async def star_employees(self, year=None, month=None) -> list[dict]:
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
                WITH employee_metrics AS (
                    SELECT employee_id, employee_name AS name, department,
                           AVG(ftr_flag) * 100 AS achievement,
                           AVG(ftr_flag) * 100 AS ftr_rate,
                           AVG(rework_flag) * 100 AS rework_rate
                    FROM timesheets
                    {where_clause}
                    GROUP BY employee_id, employee_name, department
                )
                SELECT employee_id, name, department, achievement, ftr_rate, rework_rate
                FROM employee_metrics
                WHERE achievement > 90 AND ftr_rate > 90 AND rework_rate < 5
                ORDER BY achievement DESC, ftr_rate DESC
            """
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"EmployeeAnalytics star_employees failed: {e}")
            return []

    async def employee_full_profile(self, employee_id: str) -> dict:
        try:
            sql = """
                SELECT 
                    employee_name AS name,
                    department,
                    AVG(ftr_flag) * 100 AS overall_achievement,
                    AVG(ftr_flag) * 100 AS ftr_rate,
                    AVG(rework_flag) * 100 AS rework_rate,
                    CASE WHEN AVG(eta_hours / NULLIF(actual_hours, 0)) * 100 > 100 
                         THEN 100 
                         ELSE AVG(eta_hours / NULLIF(actual_hours, 0)) * 100 
                    END AS eta_adherence,
                    SUM(actual_hours) / (COALESCE(NULLIF(COUNT(DISTINCT (year || '-' || month)), 0), 1) * 160.0) * 100 AS utilization,
                    COUNT(DISTINCT (year || '-' || month)) AS months_active,
                    COUNT(*) AS tasks_completed
                FROM timesheets
                WHERE employee_id = ?
                GROUP BY employee_id, employee_name, department
            """
            result = await self.query_service.execute_query(sql, [employee_id])
            return result[0] if result else {}
        except Exception as e:
            logger.error(f"EmployeeAnalytics employee_full_profile failed: {e}")
            return {}
