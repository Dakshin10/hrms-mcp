from fastapi import FastAPI

from src.api.routes.employees import router as employee_router

app = FastAPI(
    title="Minori HRMS MCP",
    version="1.0.0"
)

app.include_router(
    employee_router,
    tags=["Employees"]
)