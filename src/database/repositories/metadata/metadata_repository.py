from src.database.repositories.base_repository import (
    BaseRepository
)


class MetadataRepository(BaseRepository):

    async def get_tables(self):
        return await self.db.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            AND name != '_cf_KV'
            ORDER BY name
            """
        )

    async def get_table_schema(
        self,
        table_name: str
    ):
        return await self.db.execute(
            f"""
            PRAGMA table_info({table_name})
            """
        )

    async def get_row_count(
        self,
        table_name: str
    ):
        return await self.db.execute(
            f"""
            SELECT COUNT(*) as total
            FROM {table_name}
            """
        )