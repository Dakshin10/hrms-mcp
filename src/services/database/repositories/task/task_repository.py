from src.services.database.repositories.base_repository import (
    BaseRepository
)


class TaskRepository(BaseRepository):

    async def create_task(
        self,
        task: dict
    ):
        return await self.db.execute(
            """
            INSERT INTO task_logs (
                employee_name,
                role,
                task_description,
                category,
                assumptions,
                actual_hours,
                eta,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                task["employee_name"],
                task["role"],
                task["task_description"],
                task["category"],
                task["assumptions"],
                task["actual_hours"],
                task["eta"],
                task["confidence"]
            ]
        )

    async def get_tasks_by_employee(
        self,
        employee_name: str
    ):
        return await self.db.execute(
            """
            SELECT *
            FROM task_logs
            WHERE employee_name = ?
            ORDER BY actual_hours DESC
            """,
            [employee_name]
        )

    async def get_tasks_by_category(
        self,
        category: str
    ):
        return await self.db.execute(
            """
            SELECT *
            FROM task_logs
            WHERE category = ?
            """,
            [category]
        )