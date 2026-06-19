import asyncio

from src.mcp_server.tools.employees.get_employee_profile import (
    get_employee_profile
)


async def main():

    result = await get_employee_profile(
        "EMP0001"
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())