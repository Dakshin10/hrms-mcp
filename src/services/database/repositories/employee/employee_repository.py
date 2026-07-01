from src.services.database.repositories.base_repository import BaseRepository


class EmployeeRepository(BaseRepository):

    async def create_employee(
        self,
        employee: dict
    ):
        return await self.db.execute(
            """
            INSERT INTO employees (
                employee_id,
                employee_name,
                department,
                designation,
                salary
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                employee["employee_id"],
                employee["employee_name"],
                employee["department"],
                employee["designation"],
                employee["salary"]
            ]
        )

    async def employee_exists(
        self,
        employee_id: str
    ):
        result = await self.db.execute(
            """
            SELECT employee_id
            FROM employees
            WHERE employee_id = ?
            """,
            [employee_id]
        )

        return len(result["results"]) > 0

    async def get_employee_by_id(
        self,
        employee_id: str
    ):
        return await self.db.execute(
            """
            SELECT *
            FROM employees
            WHERE employee_id = ?
            """,
            [employee_id]
        )

    async def get_all_employees(self):
        return await self.db.execute(
            """
            SELECT *
            FROM employees
            ORDER BY employee_id
            """
        )

    async def get_employees_by_department(
        self,
        department: str
    ):
        return await self.db.execute(
            """
            SELECT *
            FROM employees
            WHERE LOWER(department) = LOWER(?)
            ORDER BY employee_name
            """,
            [department]
        )

    async def search_employees(
        self,
        keyword: str
    ):
        return await self.db.execute(
            """
            SELECT *
            FROM employees
            WHERE
                employee_name LIKE ?
                OR department LIKE ?
                OR designation LIKE ?
            ORDER BY employee_name
            LIMIT 50
            """,
            [
                f"%{keyword}%",
                f"%{keyword}%",
                f"%{keyword}%"
            ]
        )