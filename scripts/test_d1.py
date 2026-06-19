# scripts/test_d1.py

import asyncio

from src.database.d1_client import D1Client


async def main():
    db = D1Client()

    result = await db.execute(
        "SELECT COUNT(*) as total FROM employees"
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())