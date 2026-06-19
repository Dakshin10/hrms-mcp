import logging
import json
from src.core.config.settings import settings

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include trace dict if attached to log record
        if hasattr(record, "trace"):
            log_record["trace"] = record.trace
        return json.dumps(log_record)

# Create and configure the custom logger
logger = logging.getLogger("minori-hrms-mcp")
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

# Clear existing handlers to avoid duplicates during hot reloads
if logger.handlers:
    logger.handlers.clear()

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.propagate = False