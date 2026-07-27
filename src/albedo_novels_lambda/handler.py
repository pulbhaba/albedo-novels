from __future__ import annotations

import json
from typing import Any


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod")
    path = event.get("rawPath") or event.get("path") or "/"

    if method == "GET" and path == "/health":
        return json_response(200, {"status": "ok", "service": "albedo-novel-service"})

    return json_response(
        501,
        {
            "error": "not_implemented",
            "message": "Route is planned but not implemented yet.",
            "method": method,
            "path": path,
        },
    )


def json_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }
