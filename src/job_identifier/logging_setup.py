from __future__ import annotations
import json
import logging
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Promote any extra attributes
        for k, v in record.__dict__.items():
            if k in {"args", "msg", "name", "levelname", "levelno", "pathname",
                     "filename", "module", "exc_info", "exc_text", "stack_info",
                     "lineno", "funcName", "created", "msecs", "relativeCreated",
                     "thread", "threadName", "processName", "process",
                     "taskName", "message", "asctime"}:
                continue
            payload[k] = v
        return json.dumps(payload)


def setup_run_logger(run_id: str, log_dir: Path) -> tuple[logging.Logger, logging.Handler]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{run_id}.log"
    handler = logging.FileHandler(log_file)
    handler.setFormatter(_JsonFormatter())
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("job_identifier")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger, handler
