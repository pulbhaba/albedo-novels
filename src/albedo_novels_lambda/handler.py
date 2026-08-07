from __future__ import annotations

import json
from typing import Any

from albedo_novels_infrastructure.auth import JwtAuthenticator
from albedo_novels_infrastructure.composition import build_use_cases
from albedo_novels_infrastructure.http import HttpApplication, HttpRequest, HttpResponse


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    request = HttpRequest(
        method=_method(event),
        path=_path(event),
        headers=_headers(event),
        query=_query(event),
    )
    return _lambda_response(_application().handle(request))


def _application() -> HttpApplication:
    return HttpApplication(build_use_cases(), JwtAuthenticator())


def _lambda_response(response: HttpResponse) -> dict[str, Any]:
    return {
        "statusCode": response.status_code,
        "headers": {"Content-Type": "application/json", **response.headers},
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
