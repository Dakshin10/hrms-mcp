import os
import pandas as pd
from src.core.logging.logger import logger
from src.services.database.repositories.employee.employee_repository import EmployeeRepository
from src.services.database.repositories.import_history_repository import ImportHistoryRepository


class HRMSCSVLoader:

    def __init__(self):
        self.employee_repo = EmployeeRepository()
        self.import_repo = ImportHistoryRepository()

    async def load(self, csv_path: str):
        if not os.path.exists(csv_path):
            logger.error(f"CSV import file not found at: {csv_path}")
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Failed to read CSV file {csv_path}: {e}")
            raise ValueError(f"Invalid CSV format: {e}") from e

        inserted = 0
        skipped = 0
        failed = 0
        source_name = os.path.basename(csv_path)

        for idx, row in df.iterrows():
            try:
                employee_id = str(row["Employee_ID"]).strip()

                exists = await self.employee_repo.employee_exists(employee_id)
                if exists:
                    skipped += 1
                    continue

                employee = {
                    "employee_id": employee_id,
                    "first_name": str(row["First_Name"]),
                    "last_name": str(row["Last_Name"]),
                    "email": str(row["Email"]).lower(),
                    "phone_number": str(row["Phone_Number"]),
                    "department": str(row["Department"]),
                    "job_title": str(row["Job_Title"]),
                    "employment_type": str(row["Employment_Type"]),
                    "date_of_joining": str(row["Date_of_Joining"]),
                    "date_of_birth": str(row["Date_of_Birth"]),
                    "gender": str(row["Gender"]),
                    "annual_salary_inr": int(row["Annual_Salary_INR"]),
                    "manager_id": None
                    if str(row["Manager_ID"]).strip() in ("—", "", "nan", "None")
                    else str(row["Manager_ID"]),
                    "status": str(row["Status"]).upper(),
                    "location": str(row["Location"])
                }

                await self.employee_repo.create_employee(employee)
                inserted += 1

            except Exception as e:
                failed += 1
                logger.error(
                    f"Row {idx + 1} processing failed in {source_name} "
                    f"(Employee ID: {row.get('Employee_ID', 'N/A')}): {e}"
                )

        await self.import_repo.create_import_record(
            source_name=source_name,
            rows_processed=len(df),
            rows_inserted=inserted,
            rows_failed=failed
        )

        logger.info(
            f"CSV loader completed for {source_name}. Total: {len(df)}, "
            f"Inserted: {inserted}, Skipped: {skipped}, Failed: {failed}"
        )

        return {
            "processed": len(df),
            "inserted": inserted,
            "skipped": skipped,
            "failed": failed
        }