from pydantic import BaseModel


class EmployeeImportSchema(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    email: str
    phone_number: str | None = None
    department: str
    job_title: str
    employment_type: str
    date_of_joining: str
    date_of_birth: str | None = None
    gender: str | None = None
    annual_salary_inr: int | None = None
    manager_id: str | None = None
    status: str
    location: str | None = None