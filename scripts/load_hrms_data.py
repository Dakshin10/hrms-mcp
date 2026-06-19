import asyncio

from src.services.sync.hrms_csv_loader import (
    HRMSCSVLoader
)


async def main():

    loader = HRMSCSVLoader()

    result = await loader.load(
        "data/seed/HRMS_75_Records_claude.csv"
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())