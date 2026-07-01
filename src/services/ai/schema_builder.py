import time
from src.core.config.settings import settings
from src.core.logging.logger import logger
from src.services.database.metadata_service import MetadataService


class SchemaBuilder:
    def __init__(self, metadata_service: MetadataService):
        self.metadata_service = metadata_service
        self._cache: dict[str, list[dict]] | None = None
        self._cached_at: float = 0.0
        self._ttl: int = settings.schema_cache_ttl_seconds

    def _is_cache_valid(self) -> bool:
        if self._cache is None:
            return False
        return (time.time() - self._cached_at) < self._ttl

    async def get_full_schema(self) -> dict[str, list[dict]]:
        """
        Fetches the complete database schema and caches it.
        """
        if self._is_cache_valid() and self._cache is not None:
            logger.debug("Schema cache hit")
            return self._cache

        logger.info("Schema cache miss. Fetching schema from database...")
        try:
            tables_info = await self.metadata_service.get_tables()
            table_names = [t["name"] for t in tables_info if "name" in t]

            schema = {}
            for name in table_names:
                columns = await self.metadata_service.get_table_schema(name)
                schema[name] = columns

            self._cache = schema
            self._cached_at = time.time()
            return schema
        except Exception as e:
            logger.error(f"Failed to fetch database schema: {e}")
            if self._cache is not None:
                logger.warning("Returning stale cached schema due to fetch failure")
                return self._cache
            raise

    async def get_schema_for_tables(self, table_names: list[str]) -> dict[str, list[dict]]:
        """
        Returns the schema scoped to the list of table names requested.
        """
        full_schema = await self.get_full_schema()
        return {t: full_schema[t] for t in table_names if t in full_schema}

    def get_schema_as_prompt_string(self, schema: dict[str, list[dict]]) -> str:
        """
        Formats schema dictionary into a readable string for the LLM.
        """
        parts = []
        for table, columns in schema.items():
            col_defs = []
            for col in columns:
                col_name = col.get("name", "")
                col_type = col.get("type", "TEXT")
                is_pk = " [PK]" if col.get("pk") == 1 else ""
                is_notnull = " NOT NULL" if col.get("notnull") == 1 else ""
                col_defs.append(f"  - {col_name} ({col_type}){is_pk}{is_notnull}")

            columns_str = "\n".join(col_defs)
            parts.append(f"Table: {table}\nColumns:\n{columns_str}")
        return "\n\n".join(parts)

    def invalidate(self):
        logger.info("Schema cache invalidated")
        self._cache = None
        self._cached_at = 0.0
        # Also clear the metadata-service layer so both caches are reset together
        try:
            self.metadata_service.clear_cache()
        except Exception:
            pass


def discover_relationships(schema: dict[str, list[dict]]) -> list[str]:
    """
    Examines the schema and automatically detects potential relationships
    between tables based on shared column names.
    """
    relationships = []
    tables = list(schema.keys())
    for i in range(len(tables)):
        for j in range(i + 1, len(tables)):
            t1 = tables[i]
            t2 = tables[j]
            cols1 = {col.get("name", "").lower() for col in schema[t1] if col.get("name")}
            cols2 = {col.get("name", "").lower() for col in schema[t2] if col.get("name")}
            
            # Find shared columns
            shared = cols1 & cols2
            for col in shared:
                # If the column contains 'id' or '_id', or if it's a known join column
                if "id" in col or col in ("code", "name", "email", "department"):
                    relationships.append(
                        f"- `{t1}` can be joined with `{t2}` on `{t1}.{col} = {t2}.{col}`"
                    )
    return relationships
