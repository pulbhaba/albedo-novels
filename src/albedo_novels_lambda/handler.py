from __future__ import annotations

import base64
import json
import logging
from time import perf_counter
from typing import Any

from albedo_novels_infrastructure.auth import JwtAuthenticator
from albedo_novels_infrastructure.composition import build_content_use_cases, build_use_cases
from albedo_novels_infrastructure.config import cors_headers, cors_preflight_headers
from albedo_novels_infrastructure.http import HttpApplication, HttpRequest, HttpResponse
from albedo_novels_infrastructure.observability import configure_logging


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    logger = configure_logging()
    request = HttpRequest(
        method=_method(event),
        path=_path(event),
        headers=_headers(event),
        query=_query(event),
        body=_body(event),
    )
    started = perf_counter()
    request_id = getattr(_context, "aws_request_id", None)
    failed = False
    logger.info(
        "request started",
        extra={"event": "request.started", "method": request.method, "path": request.path, "request_id": request_id},
    )
    response: HttpResponse | None = None
    try:
        if request.method == "OPTIONS":
            response = HttpResponse(204, {}, cors_preflight_headers(request.headers))
        else:
            response = _application().handle(request)
        return _lambda_response(response, request.headers)
    except Exception:
        failed = True
        logger.exception(
            "request failed unexpectedly",
            extra={
                "event": "request.exception",
                "method": request.method,
                "path": request.path,
                "request_id": request_id,
            },
        )
        raise
    finally:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.log(
            logging.ERROR
            if failed
            else logging.WARNING
            if response is not None and response.status_code >= 400
            else logging.INFO,
            "request failed"
            if failed
            else "request completed"
            if response is not None
            else "request terminated",
            extra={
                "event": "request.failed"
                if failed
                else "request.completed"
                if response is not None
                else "request.terminated",
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code if response is not None and not failed else 500,
                "duration_ms": duration_ms,
                "request_id": request_id,
            },
        )


def _application() -> HttpApplication:
    return HttpApplication(build_use_cases(), JwtAuthenticator(), build_content_use_cases())


def _lambda_response(response: HttpResponse, request_headers: dict[str, str] | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", **response.headers}
    headers.update(cors_headers(request_headers or {}))
    return {
        "statusCode": response.status_code,
        "headers": headers,
        "body": json.dumps(response.body),
    }


def _method(event: dict[str, Any]) -> str:
    request_context = event.get("requestContext") or {}
    http = request_context.get("http") or {}
    return str(http.get("method") or event.get("httpMethod") or "").upper()


def _path(event: dict[str, Any]) -> str:
    return str(event.get("rawPath") or event.get("path") or "/")


def _headers(event: dict[str, Any]) -> dict[str, str]:
    return {str(name): str(value) for name, value in (event.get("headers") or {}).items()}


def _query(event: dict[str, Any]) -> dict[str, str]:
    return {str(name): str(value) for name, value in (event.get("queryStringParameters") or {}).items()}


def _body(event: dict[str, Any]) -> object:
    raw_body = event.get("body")
    if raw_body in (None, ""):
        return None
    if event.get("isBase64Encoded"):
        try:
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    try:
        return json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    except json.JSONDecodeError:
        return None
