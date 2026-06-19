from src.database.repositories.metadata.metadata_repository import (
    MetadataRepository
)


class MetadataService:

    def __init__(self):
        self.repo = MetadataRepository()

    async def get_tables(self):
        result = await self.repo.get_tables()
        return result.get("results", [])

    async def get_table_schema(
        self,
        table_name: str
    ):
        result = await self.repo.get_table_schema(
            table_name
        )

        return result.get("results", [])

    async def get_row_count(
        self,
        table_name: str
    ):
        result = await self.repo.get_row_count(
            table_name
        )

        return result.get("results", [])


metadata_service = MetadataService()