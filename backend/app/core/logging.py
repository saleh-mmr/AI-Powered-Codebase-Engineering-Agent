import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "route",
            "status_code",
            "duration_ms",
            "error_type",
            "job_id",
            "attempt",
            "files_stored",
            "symbol_count",
            "chunk_count",
            "input_tokens",
            "estimated_cost_usd",
            "result_count",
            "error_code",
        ):
            if hasattr(record, key):
                event[key] = getattr(record, key)
        return json.dumps(event)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("repopilot")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
