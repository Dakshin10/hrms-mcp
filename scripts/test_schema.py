import asyncio

from src.services.metadata.metadata_service import (
    MetadataService
)


async def main():

    service = MetadataService()

    schema = await service.get_table_schema(
        "employees"
    )

    print(schema)


if __name__ == "__main__":
    asyncio.run(main())