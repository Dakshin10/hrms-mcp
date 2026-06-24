import os
import pandas as pd
from src.core.logging.logger import logger
from src.services.database.sync.column_map import TIMESHEET_COLUMN_MAP, REQUIRED_COLUMNS


class TimesheetLoader:
    def __init__(self, d1_client, batch_size=50):
        self.d1_client = d1_client
        self.batch_size = batch_size

    async def load_file(self, file_path: str) -> dict:
        filename = os.path.basename(file_path)
        if not os.path.exists(file_path):
            logger.error(f"File not found for timesheet load: {file_path}")
            return {
                "file": filename,
                "total_rows": 0,
                "loaded": 0,
                "skipped": 0,
                "errors": [f"File not found: {file_path}"]
            }

        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                return {
                    "file": filename,
                    "total_rows": 0,
                    "loaded": 0,
                    "skipped": 0,
                    "errors": [f"Unsupported file format: {file_path}"]
                }
        except Exception as e:
            logger.error(f"Failed to read timesheet file: {e}")
            return {
                "file": filename,
                "total_rows": 0,
                "loaded": 0,
                "skipped": 0,
                "errors": [f"Failed to parse file: {e}"]
            }

        total_rows = len(df)
        df_normalized = self._normalize_columns(df)
        df_valid, skipped_count = self._validate_rows(df_normalized)

        loaded_count, errors = await self._load_batches(df_valid)

        logger.info(
            f"Timesheet loader completed for {filename}. "
            f"Loaded: {loaded_count}, Skipped: {skipped_count}, Errors: {len(errors)}"
        )

        return {
            "file": filename,
            "total_rows": total_rows,
            "loaded": loaded_count,
            "skipped": skipped_count,
            "errors": errors
        }

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        # Strip whitespace from column headers
        df = df.rename(columns=lambda x: str(x).strip())

        # Map input headers case-insensitively
        rename_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in TIMESHEET_COLUMN_MAP:
                rename_map[col] = TIMESHEET_COLUMN_MAP[col_lower]

        df = df.rename(columns=rename_map)

        # Retain only recognized columns mapped to schema
        target_columns = list(set(TIMESHEET_COLUMN_MAP.values()))
        keep_columns = [c for c in df.columns if c in target_columns]
        return df[keep_columns]

    def _validate_rows(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        valid_rows = []
        skipped_count = 0

        for idx, row in df.iterrows():
            missing = []
            for col in REQUIRED_COLUMNS:
                val = row.get(col)
                # Check for NaN, None, or empty strings
                if pd.isna(val) or str(val).strip() == "":
                    missing.append(col)

            if missing:
                skipped_count += 1
                logger.warning(
                    f"Timesheet loader row {idx} skipped: "
                    f"Missing required columns {missing}"
                )
            else:
                valid_rows.append(row)

        if valid_rows:
            valid_df = pd.DataFrame(valid_rows).reset_index(drop=True)
        else:
            # Return empty DataFrame with original columns
            valid_df = pd.DataFrame(columns=df.columns)

        return valid_df, skipped_count

    async def _load_batches(self, df: pd.DataFrame) -> tuple[int, list[str]]:
        loaded_count = 0
        errors = []

        cols = [
            "employee_id", "employee_name", "task_name", "department",
            "eta_hours", "actual_hours", "ftr_flag", "rework_flag",
            "task_status", "completion_date", "month", "year"
        ]

        total_len = len(df)
        for i in range(0, total_len, self.batch_size):
            batch = df.iloc[i : i + self.batch_size]
            placeholders = []
            params = []

            for _, row in batch.iterrows():
                row_placeholders = []
                for col in cols:
                    val = row.get(col)
                    if pd.isna(val):
                        val = None

                    # Normalize flags to integer (0 or 1)
                    if col in ("ftr_flag", "rework_flag") and val is not None:
                        val_str = str(val).strip().lower()
                        if val_str in ("true", "1", "1.0", "yes"):
                            val = 1
                        elif val_str in ("false", "0", "0.0", "no"):
                            val = 0
                        else:
                            try:
                                val = int(float(val))
                            except ValueError:
                                val = 0

                    row_placeholders.append("?")
                    params.append(val)

                placeholders.append(f"({', '.join(row_placeholders)})")

            if not placeholders:
                continue

            sql = f"""
                INSERT OR REPLACE INTO timesheets ({', '.join(cols)})
                VALUES {', '.join(placeholders)}
            """

            try:
                await self.d1_client.execute(sql, params)
                loaded_count += len(batch)
            except Exception as e:
                err_msg = f"Failed to execute timesheets batch starting at index {i}: {e}"
                logger.error(err_msg)
                errors.append(err_msg)

        return loaded_count, errors
