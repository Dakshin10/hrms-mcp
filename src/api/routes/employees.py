from fastapi import APIRouter

from src.services.employee.employee_service import (
    EmployeeService
)

router = APIRouter()

employee_service = EmployeeService()


@router.get("/employees")
async def get_all_employees():
    return await employee_service.get_all_employees()


@router.get("/employees/search/{keyword}")
async def search_employees(
    keyword: str
):
    return await employee_service.search_employees(
        keyword
    )


@router.get("/employees/department/{department}")
async def get_department_employees(
    department: str
):
    return await employee_service.get_employees_by_department(
        department
    )


@router.get("/employees/id/{employee_id}")
async def get_employee(
    employee_id: str
):
    return await employee_service.get_employee_by_id(
        employee_id
    )