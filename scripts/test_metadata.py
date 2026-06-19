import asyncio

from src.services.metadata.metadata_service import (
    MetadataService
)


async def main():

    service = MetadataService()

    tables = await service.get_tables()

    print(tables)


if __name__ == "__main__":
    asyncio.run(main())