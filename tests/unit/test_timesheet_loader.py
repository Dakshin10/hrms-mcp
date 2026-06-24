import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import tempfile
import os
from src.services.database.sync.timesheet_loader import TimesheetLoader


class TestTimesheetLoader(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.execute = AsyncMock(return_value={"success": True})
        self.loader = TimesheetLoader(self.mock_db, batch_size=2)

    def test_normalize_columns_mapping(self):
        df = pd.DataFrame({
            "Employee ID": ["EMP001"],
            "Task Name": ["Coding"],
            "Hours Logged": [8.0],
            "UnmappedCol": ["Random"]
        })
        normalized = self.loader._normalize_columns(df)
        self.assertIn("employee_id", normalized.columns)
        self.assertIn("task_name", normalized.columns)
        self.assertIn("actual_hours", normalized.columns)
        self.assertNotIn("UnmappedCol", normalized.columns)

    def test_validate_rows_drops_nulls(self):
        df = pd.DataFrame([
            {"employee_id": "EMP001", "task_name": "Coding", "actual_hours": 8.0},
            {"employee_id": None, "task_name": "Design", "actual_hours": 4.0},
            {"employee_id": "EMP002", "task_name": "", "actual_hours": 3.0},
            {"employee_id": "EMP003", "task_name": "Review", "actual_hours": None}
        ])
        valid_df, skipped = self.loader._validate_rows(df)
        self.assertEqual(len(valid_df), 1)
        self.assertEqual(skipped, 3)
        self.assertEqual(valid_df.iloc[0]["employee_id"], "EMP001")

    async def async_test_load_file_mock_csv(self):
        df_data = pd.DataFrame([
            {"Emp ID": "EMP001", "Task Name": "Coding", "Hours Logged": 8.0, "Department": "Engineering"},
            {"Emp ID": "EMP002", "Task Name": "Review", "Hours Logged": 2.0, "Department": "QA"}
        ])

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            df_data.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            res = await self.loader.load_file(temp_path)
            self.assertEqual(res["total_rows"], 2)
            self.assertEqual(res["loaded"], 2)
            self.assertEqual(res["skipped"], 0)
            self.assertEqual(len(res["errors"]), 0)
            self.assertEqual(self.mock_db.execute.call_count, 1)
        finally:
            os.remove(temp_path)

    def test_load_file_mock_csv(self):
        import asyncio
        asyncio.run(self.async_test_load_file_mock_csv())

    async def async_test_batch_error_isolation(self):
        # We have 4 rows, batch size 2 -> 2 batches
        df = pd.DataFrame([
            {"employee_id": "EMP001", "task_name": "Coding", "actual_hours": 8.0},
            {"employee_id": "EMP002", "task_name": "Review", "actual_hours": 2.0},
            {"employee_id": "EMP003", "task_name": "Deploy", "actual_hours": 4.0},
            {"employee_id": "EMP004", "task_name": "Support", "actual_hours": 6.0}
        ])

        # First execution succeeds, second fails, third succeeds? Wait, we have 2 batches.
        # Let's mock execute side effect to fail on second call
        call_count = 0
        async def mock_execute(sql, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("DB Write Error")
            return {"success": True}

        self.mock_db.execute = AsyncMock(side_effect=mock_execute)
        
        loaded_count, errors = await self.loader._load_batches(df)
        self.assertEqual(loaded_count, 2)  # First batch of 2 loaded
        self.assertEqual(len(errors), 1)   # Second batch failed

    def test_batch_error_isolation(self):
        import asyncio
        asyncio.run(self.async_test_batch_error_isolation())


if __name__ == "__main__":
    unittest.main()
