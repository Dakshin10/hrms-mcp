from src.services.database.metadata_service import metadata_service
from src.services.ai.table_selector import TableSelector
from src.services.ai.schema_builder import SchemaBuilder
from src.services.ai.prompt_builder import PromptBuilder
from src.services.ai.llm_service import LLMService
from src.services.ai.sql_validator import SQLValidator
from src.services.ai.observability import QueryObserver
from src.services.ai.query_cache import QueryCache
from src.services.ai.fast_path import FastPathHandler
from src.services.ai.answer_generator import answer_generator

table_selector = TableSelector()
schema_builder = SchemaBuilder(metadata_service)
prompt_builder = PromptBuilder()
llm_service = LLMService()
sql_validator = SQLValidator()
query_observer = QueryObserver()
query_cache = QueryCache()
fast_path_handler = FastPathHandler()
