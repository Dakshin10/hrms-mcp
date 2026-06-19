from src.database.repositories.base_repository import (
    BaseRepository
)


class TimesheetRepository(BaseRepository):

    async def create_summary(
        self,
        summary: dict
    ):
        return await self.db.execute(
            """
            INSERT INTO timesheet_summary (
                employee_name,
                role,
                month,
                total_tasks,
                total_hours,
                rework_tasks,
                utilization_percentage
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                summary["employee_name"],
                summary["role"],
                summary["month"],
                summary["total_tasks"],
                summary["total_hours"],
                summary["rework_tasks"],
                summary["utilization_percentage"]
            ]
        )

    async def get_top_utilization(
        self,
        limit: int = 10
    ):
        return await self.db.execute(
            """
            SELECT *
            FROM timesheet_summary
            ORDER BY utilization_percentage DESC
            LIMIT ?
            """,
            [limit]
        )

    async def get_employee_summary(
        self,
        employee_name: str
    ):
        return await self.db.execute(
            """
            SELECT *
            FROM timesheet_summary
            WHERE employee_name = ?
            """,
            [employee_name]
        )