from __future__ import annotations

import json
import logging
import sys
from unittest.mock import Mock, patch

import pytest

from albedo_novels_infrastructure.observability import JsonFormatter
from albedo_novels_lambda.handler import lambda_handler


def test_json_formatter_emits_queryable_request_fields() -> None:
    record = logging.LogRecord(
        "albedo_novels", logging.INFO, "handler.py", 1, "request completed", (), None
    )
    record.event = "request.completed"
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.duration_ms = 1.25
    record.request_id = "request-123"

    payload = json.loads(JsonFormatter().format(record))

    assert payload == {
        "duration_ms": 1.25,
        "event": "request.completed",
        "level": "INFO",
        "logger": "albedo_novels",
        "message": "request completed",
        "method": "GET",
        "path": "/health",
        "request_id": "request-123",
        "status_code": 200,
    }


def test_json_formatter_includes_exception_details() -> None:
    try:
        raise RuntimeError("database unavailable")
    except RuntimeError:
        record = logging.LogRecord(
            "albedo_novels", logging.ERROR, "handler.py", 1, "request failed", (), None
        )
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonFormatter().format(record))

    assert payload["exception"].endswith("RuntimeError: database unavailable")


def test_lambda_handler_logs_unexpected_failures_before_reraising() -> None:
    logger = Mock()
    with patch("albedo_novels_lambda.handler.configure_logging", return_value=logger):
        with patch(
            "albedo_novels_lambda.handler._application",
            side_effect=RuntimeError("database unavailable"),
        ):
            with pytest.raises(RuntimeError, match="database unavailable"):
                lambda_handler(
                    {
                        "requestContext": {"http": {"method": "GET"}},
                        "rawPath": "/health",
                        "headers": {},
                    },
                    None,
                )

    logger.exception.assert_called_once()
    completion = logger.log.call_args.kwargs["extra"]
    assert completion["event"] == "request.failed"
    assert completion["status_code"] == 500
