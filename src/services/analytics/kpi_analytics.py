from src.core.logging.logger import logger
from src.services.database.query_service import query_service as default_query_service


class KPIAnalytics:
    def __init__(self, query_service=None):
        self.query_service = query_service or default_query_service

    async def top_performers(self, limit=10, year=None, month=None) -> list[dict]:
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
                SELECT employee_id, employee_name, AVG(ftr_flag) * 100 AS achievement
                FROM timesheets
                {where_clause}
                GROUP BY employee_id, employee_name
                ORDER BY achievement DESC
                LIMIT ?
            """
            params.append(limit)
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"KPIAnalytics top_performers failed: {e}")
            return []

    async def bottom_performers(self, threshold=70, year=None, month=None) -> list[dict]:
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
                SELECT employee_id, employee_name, AVG(ftr_flag) * 100 AS achievement
                FROM timesheets
                {where_clause}
                GROUP BY employee_id, employee_name
                HAVING achievement < ?
                ORDER BY achievement ASC
            """
            params.append(threshold)
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"KPIAnalytics bottom_performers failed: {e}")
            return []

    async def department_kpi_ranking(self, year=None, month=None) -> list[dict]:
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
                SELECT department, AVG(ftr_flag) * 100 AS avg_achievement
                FROM timesheets
                {where_clause}
                GROUP BY department
                ORDER BY avg_achievement DESC
            """
            return await self.query_service.execute_query(sql, params)
        except Exception as e:
            logger.error(f"KPIAnalytics department_kpi_ranking failed: {e}")
            return []

    async def employee_kpi_trend(self, employee_id: str) -> list[dict]:
        try:
            sql = """
                SELECT year, month, AVG(ftr_flag) * 100 AS achievement
                FROM timesheets
                WHERE employee_id = ?
                GROUP BY year, month
                ORDER BY year ASC, month ASC
            """
            return await self.query_service.execute_query(sql, [employee_id])
        except Exception as e:
            logger.error(f"KPIAnalytics employee_kpi_trend failed: {e}")
            return []

    async def kpi_distribution(self, year=None, month=None) -> list[dict]:
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
                WITH employee_achievements AS (
                    SELECT employee_id, AVG(ftr_flag) * 100 AS achievement
                    FROM timesheets
                    {where_clause}
                    GROUP BY employee_id
                )
                SELECT 
                    SUM(CASE WHEN achievement >= 0 AND achievement < 50 THEN 1 ELSE 0 END) AS band_0_50,
                    SUM(CASE WHEN achievement >= 50 AND achievement < 70 THEN 1 ELSE 0 END) AS band_50_70,
                    SUM(CASE WHEN achievement >= 70 AND achievement < 85 THEN 1 ELSE 0 END) AS band_70_85,
                    SUM(CASE WHEN achievement >= 85 AND achievement <= 100 THEN 1 ELSE 0 END) AS band_85_100
                FROM employee_achievements
            """
            result = await self.query_service.execute_query(sql, params)
            if result:
                row = result[0]
                return [
                    {"band": "0-50%", "count": row.get("band_0_50") or 0},
                    {"band": "50-70%", "count": row.get("band_50_70") or 0},
                    {"band": "70-85%", "count": row.get("band_70_85") or 0},
                    {"band": "85-100%", "count": row.get("band_85_100") or 0}
                ]
            return []
        except Exception as e:
            logger.error(f"KPIAnalytics kpi_distribution failed: {e}")
            return []
