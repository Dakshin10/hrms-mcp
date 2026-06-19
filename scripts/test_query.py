import asyncio

from src.services.query.query_service import (
    QueryService
)


async def main():

    service = QueryService()

    result = await service.execute_query(
        """
        SELECT
            employee_id,
            first_name,
            department
        FROM employees
        LIMIT 5
        """
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())