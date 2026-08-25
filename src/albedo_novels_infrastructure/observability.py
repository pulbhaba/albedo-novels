"""Structured application logging for the Lambda adapter."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


LOGGER_NAME = "albedo_novels"
_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line for CloudWatch Insights."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for field in ("event", "method", "path", "status_code", "duration_ms", "request_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging() -> logging.Logger:
    """Configure a process-wide JSON logger once per warm Lambda runtime."""
    global _CONFIGURED
    logger = logging.getLogger(LOGGER_NAME)
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        _CONFIGURED = True
    return logger
