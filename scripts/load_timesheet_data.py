import asyncio
import pandas as pd

from src.database.repositories.timesheet.timesheet_repository import (
    TimesheetRepository
)

from src.database.repositories.task.task_repository import (
    TaskRepository
)

from pathlib import Path

FILE_PATH = Path(
    "data/seed/data_report.xlsx"
)


async def load_timesheet():

    timesheet_repo = TimesheetRepository()
    task_repo = TaskRepository()

    df = pd.read_excel(FILE_PATH)
    print(df.head(20))
    print(df.columns)

    # Summary metrics
    total_tasks = 0
    total_hours = 0
    rework_tasks = 0
    utilization = 0

    for _, row in df.iterrows():

        first_col = str(row.iloc[0])

        if first_col == "Total tasks":
            total_tasks = int(row.iloc[1])

        elif first_col == "Total hours logged":
            total_hours = float(row.iloc[1])

        elif first_col == "Rework tasks":
            rework_tasks = int(row.iloc[1])

        elif first_col == "Utilization":
            utilization = float(
                str(row.iloc[1]).replace("%", "")
            )

    await timesheet_repo.create_summary(
        {
            "employee_name": "Unknown",
            "role": "Unknown",
            "month": "Apr-2026",
            "total_tasks": total_tasks,
            "total_hours": total_hours,
            "rework_tasks": rework_tasks,
            "utilization_percentage": utilization
        }
    )

    inserted_tasks = 0

    rows = df.values.tolist()

    for i in range(len(rows) - 1):

        row = rows[i]

        if len(row) < 6:
            continue

        task_description = row[0]

        if pd.isna(task_description):
            continue

        if task_description in [
            "Task description",
            "Total tasks",
            "Total hours logged",
            "Rework tasks",
            "Utilization"
        ]:
            continue

        employee_context = rows[i + 1][0]

        await task_repo.create_task(
            {
                "employee_name": str(employee_context),
                "role": str(employee_context),
                "task_description": str(row[0]),
                "category": str(row[1]),
                "assumptions": str(row[2]),
                "actual_hours": float(row[3]),
                "eta": str(row[4]),
                "confidence": str(row[5])
            }
        )

        inserted_tasks += 1

    print(
        f"Summary inserted successfully"
    )

    print(
        f"Tasks inserted: {inserted_tasks}"
    )


if __name__ == "__main__":
    asyncio.run(
        load_timesheet()
    )