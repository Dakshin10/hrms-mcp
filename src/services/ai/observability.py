from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from src.core.logging.logger import logger


@dataclass
class QueryTrace:
    question: str
    selected_tables: list[str]
    generated_sql: str
    validation_passed: bool
    validation_error: str | None
    d1_latency_ms: float
    llm_latency_ms: float
    total_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    row_count: int
    error: str | None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class QueryObserver:
    def log_trace(self, trace: QueryTrace):
        """
        Logs a structured QueryTrace dict to the custom JSON logger.
        """
        trace_dict = asdict(trace)
        if trace.error or not trace.validation_passed:
            logger.error(
                f"QueryTrace Failure: {trace.validation_error or trace.error}",
                extra={"trace": trace_dict}
            )
        else:
            logger.info(
                f"QueryTrace Success: '{trace.question[:60]}'",
                extra={"trace": trace_dict}
            )
