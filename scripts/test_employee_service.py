import asyncio

from src.services.employee.employee_service import (
    EmployeeService
)


async def main():

    service = EmployeeService()

    employee = await service.get_employee_by_id(
        "EMP0001"
    )

    print(employee)


if __name__ == "__main__":
    asyncio.run(main())