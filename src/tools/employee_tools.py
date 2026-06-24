from src.core.logging.logger import logger
from src.services.database.employee_service import EmployeeService

employee_service = EmployeeService()

async def get_all_employees() -> list | dict:
    """
    Get a list of all employees in the organization.
    """
    logger.info("MCP Tool get_all_employees invoked")
    try:
        employees = await employee_service.get_all_employees()
        return employees
    except Exception as e:
        logger.error(f"Error in get_all_employees: {e}")
        return {"error": str(e), "tool": "get_all_employees"}


async def get_employee_by_id(employee_id: str) -> dict | None:
    """
    Get detailed information for a specific employee by their employee ID (e.g. EMP0001).
    """
    logger.info(f"MCP Tool get_employee_by_id invoked for: {employee_id}")
    try:
        employee = await employee_service.get_employee_by_id(employee_id)
        return employee
    except Exception as e:
        logger.error(f"Error in get_employee_by_id: {e}")
        return {"error": str(e), "tool": "get_employee_by_id"}


async def get_employees_by_department(department: str) -> list | dict:
    """
    Get all employees belonging to a specific department.
    """
    logger.info(f"MCP Tool get_employees_by_department invoked for: {department}")
    try:
        employees = await employee_service.get_employees_by_department(department)
        return employees
    except Exception as e:
        logger.error(f"Error in get_employees_by_department: {e}")
        return {"error": str(e), "tool": "get_employees_by_department"}


async def search_employees(keyword: str) -> list | dict:
    """
    Search employees by keyword matching first name, last name, email, department, or job title.
    """
    logger.info(f"MCP Tool search_employees invoked with keyword: {keyword}")
    try:
        employees = await employee_service.search_employees(keyword)
        return employees
    except Exception as e:
        logger.error(f"Error in search_employees: {e}")
        return {"error": str(e), "tool": "search_employees"}
