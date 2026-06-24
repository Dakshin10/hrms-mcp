from src.services.database.repositories.base_repository import (
    BaseRepository
)


class QueryRepository(BaseRepository):

    async def execute_query(
        self,
        sql: str,
        params=None
    ):
        return await self.db.execute(sql, params)