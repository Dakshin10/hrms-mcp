from src.database.repositories.employee.employee_repository import (
    EmployeeRepository
)


class EmployeeService:

    def __init__(self):
        self.employee_repo = EmployeeRepository()

    async def get_employee_by_id(
        self,
        employee_id: str
    ):
        result = await self.employee_repo.get_employee_by_id(
            employee_id
        )

        rows = result["results"]

        if not rows:
            return None

        return rows[0]

    async def get_all_employees(self):
        result = await self.employee_repo.get_all_employees()

        return result["results"]

    async def get_employees_by_department(
        self,
        department: str
    ):
        result = await self.employee_repo.get_employees_by_department(
            department
        )

        return result["results"]

    async def search_employees(
        self,
        keyword: str
    ):
        result = await self.employee_repo.search_employees(
            keyword
        )

        return result["results"]