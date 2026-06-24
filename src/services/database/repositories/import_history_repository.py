from src.services.database.repositories.base_repository import BaseRepository


class ImportHistoryRepository(BaseRepository):

    async def create_import_record(
        self,
        source_name,
        rows_processed,
        rows_inserted,
        rows_failed
    ):
        return await self.db.execute(
            """
            INSERT INTO import_history (
                source_name,
                rows_processed,
                rows_inserted,
                rows_failed,
                started_at,
                completed_at
            )
            VALUES (
                ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            [
                source_name,
                rows_processed,
                rows_inserted,
                rows_failed
            ]
        )