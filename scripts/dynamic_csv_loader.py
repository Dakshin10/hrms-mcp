import asyncio
import pandas as pd
import re

from src.database.d1_client import D1Client


CSV_FILE = "data/seed/employees.csv"
TABLE_NAME = "employees_import"


def sanitize_column(column: str):
    return re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        column.strip().lower()
    )


async def create_table(
    db,
    table_name,
    columns
):
    column_defs = []

    for col in columns:
        column_defs.append(
            f'"{sanitize_column(col)}" TEXT'
        )

    sql = f"""
    CREATE TABLE IF NOT EXISTS
    {table_name}
    (
        {",".join(column_defs)}
    )
    """

    await db.execute(sql)


async def insert_rows(
    db,
    table_name,
    df
):
    columns = [
        sanitize_column(col)
        for col in df.columns
    ]

    placeholders = ",".join(
        ["?"] * len(columns)
    )

    sql = f"""
    INSERT INTO {table_name}
    (
        {",".join(columns)}
    )
    VALUES
    (
        {placeholders}
    )
    """

    for _, row in df.iterrows():

        await db.execute(
            sql,
            row.fillna("").tolist()
        )


async def main():

    db = D1Client()

    df = pd.read_csv(CSV_FILE)

    await create_table(
        db,
        TABLE_NAME,
        df.columns
    )

    await insert_rows(
        db,
        TABLE_NAME,
        df
    )

    await db.execute(
        """
        INSERT INTO imported_datasets
        (
            table_name,
            source_file,
            row_count
        )
        VALUES (?, ?, ?)
        """,
        [
            TABLE_NAME,
            CSV_FILE,
            len(df)
        ]
    )

    print(
        f"Imported {len(df)} rows into {TABLE_NAME}"
    )


if __name__ == "__main__":
    asyncio.run(main())