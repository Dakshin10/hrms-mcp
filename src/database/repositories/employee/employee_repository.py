from src.database.repositories.base_repository import BaseRepository


class EmployeeRepository(BaseRepository):

    async def create_employee(
        self,
        employee: dict
    ):
        return await self.db.execute(
            """
            INSERT INTO employees (
                employee_id,
                first_name,
                last_name,
                email,
                phone_number,
                department,
                job_title,
                employment_type,
                date_of_joining,
                date_of_birth,
                gender,
                annual_salary_inr,
                manager_id,
                status,
                location
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                employee["employee_id"],
                employee["first_name"],
                employee["last_name"],
                employee["email"],
                employee["phone_number"],
                employee["department"],
                employee["job_title"],
                employee["employment_type"],
                employee["date_of_joining"],
                employee["date_of_birth"],
                employee["gender"],
                employee["annual_salary_inr"],
                employee["manager_id"],
                employee["status"],
                employee["location"]
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
            WHERE department = ?
            ORDER BY first_name
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
                first_name LIKE ?
                OR last_name LIKE ?
                OR department LIKE ?
                OR job_title LIKE ?
            LIMIT 50
            """,
            [
                f"%{keyword}%",
                f"%{keyword}%",
                f"%{keyword}%",
                f"%{keyword}%"
            ]
        )