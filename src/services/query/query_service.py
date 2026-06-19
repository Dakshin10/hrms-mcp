from src.database.repositories.query.query_repository import (
    QueryRepository
)


class QueryService:

    def __init__(self):
        self.repo = QueryRepository()

    async def execute_query(
        self,
        sql: str,
        params=None
    ):
        result = await self.repo.execute_query(
            sql,
            params
        )

        return result.get("results", [])


query_service = QueryService()
