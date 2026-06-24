import time
from src.services.database.repositories.metadata.metadata_repository import (
    MetadataRepository
)


class MetadataService:

    def __init__(self):
        self.repo = MetadataRepository()
        self._tables_cache = None
        self._tables_cache_expires = 0.0
        self._schema_cache = {}  # table_name -> (schema, expires_at)

    async def get_tables(self):
        now = time.time()
        if self._tables_cache is not None and now < self._tables_cache_expires:
            return self._tables_cache
            
        result = await self.repo.get_tables()
        self._tables_cache = result.get("results", [])
        self._tables_cache_expires = now + 3600.0  # 1 hour TTL
        return self._tables_cache

    async def get_table_schema(
        self,
        table_name: str
    ):
        now = time.time()
        if table_name in self._schema_cache:
            schema, expires = self._schema_cache[table_name]
            if now < expires:
                return schema

        result = await self.repo.get_table_schema(
            table_name
        )
        schema = result.get("results", [])
        self._schema_cache[table_name] = (schema, now + 3600.0)  # 1 hour TTL
        return schema

    async def get_row_count(
        self,
        table_name: str
    ):
        result = await self.repo.get_row_count(
            table_name
        )

        return result.get("results", [])

    def clear_cache(self):
        self._tables_cache = None
        self._tables_cache_expires = 0.0
        self._schema_cache.clear()


metadata_service = MetadataService()