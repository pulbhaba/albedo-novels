from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from albedo_novels_core.application import ListNovelsQuery, NovelUseCases
from albedo_novels_core.domain.models import Novel, NovelStatus
from albedo_novels_infrastructure.persistence.seeded_novel_dao import dao_test
from albedo_novels_lambda.auth import (
    AuthenticationError,
    JwtConfig,
    JwtVerifier,
    bearer_token,
)


DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    method = _method(event)
    path = _path(event)
    headers = _headers(event)
    query = _query(event)

    if method == "GET" and path == "/health":
        return json_response(200, {"status": "ok", "service": "albedo-novel-service"})

    if method == "GET" and path == "/novels":
        return _dispatch_list_novels(headers, query)

    return json_response(
        501,
        {
            "error": "not_implemented",
            "message": "Route is planned but not implemented yet.",
            "method": method,
            "path": path,
        },
    )


def _dispatch_list_novels(headers: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
    unauthenticated = _authenticate(headers)
    if unauthenticated is not None:
        return unauthenticated

    command = ListNovelsQuery(
        limit=_coerce_int(query.get("limit"), default=DEFAULT_LIMIT, maximum=MAX_LIMIT),
        offset=_coerce_int(query.get("offset"), default=0, minimum=0),
    )
    page = _build_use_cases().list_novels(command)
    return json_response(
        200,
        {
            "items": [novel_to_dict(novel) for novel in page.items],
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
        },
    )


def _authenticate(headers: Mapping[str, Any]) -> dict[str, Any] | None:
    """Verify the bearer token. Returns a 401 response on failure, else None."""
    try:
        token = bearer_token(headers)
        JwtVerifier(JwtConfig.from_environment()).verify(token)
    except (AuthenticationError, ValueError) as error:
        return json_response(
            401,
            {
                "error": "unauthorized",
                "message": str(error),
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None


def _build_use_cases() -> NovelUseCases:
    return NovelUseCases(
        novels=dao_test(),
        library=EmptyLibraryRepository(),
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


class EmptyLibraryRepository:
    """Stand-in until the MySQL library adapter lands (issue #13)."""

    def save(self, entry: object) -> object:
        return entry

    def delete(self, _user_id: object, _novel_id: object) -> None:
        return None

    def list_by_user(self, _user_id: object) -> list[object]:
        return []


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class SystemClock:
    def utcnow_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()


def novel_to_dict(novel: Novel) -> dict[str, Any]:
    """Serialise a Novel domain object to the public JSON shape."""
    return {
        "id": novel.id,
        "title": novel.title,
        "author": {
            "id": novel.author.id,
            "displayName": novel.author.display_name,
        },
        "coverImageUrl": novel.cover_image_url,
        "status": novel.status.value if isinstance(novel.status, NovelStatus) else str(novel.status),
        "createdAt": novel.created_at,
        "updatedAt": novel.updated_at,
    }


def json_response(
    status_code: int,
    body: dict[str, Any],
    headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            **(headers or {}),
        },
        "body": json.dumps(body),
    }


def _method(event: Mapping[str, Any]) -> str:
    request_context = event.get("requestContext") or {}
    http = request_context.get("http") or {}
    method = http.get("method") or event.get("httpMethod") or ""
    return str(method).upper()


def _path(event: Mapping[str, Any]) -> str:
    return str(event.get("rawPath") or event.get("path") or "/")


def _headers(event: Mapping[str, Any]) -> dict[str, str]:
    raw = event.get("headers") or {}
    return {str(name): str(value) for name, value in raw.items()}


def _query(event: Mapping[str, Any]) -> dict[str, str]:
    raw = event.get("queryStringParameters") or {}
    return {str(name): str(value) for name, value in raw.items()}


def _coerce_int(
    value: object,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    if minimum is not None and parsed < minimum:
        return minimum
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed
