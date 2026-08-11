from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from albedo_novels_core.application import (
    ForbiddenError,
    ListNovelsQuery,
    NotFoundError,
    NovelUseCases,
)
from albedo_novels_core.application.ports import Authenticator
from albedo_novels_core.domain.models import Novel, NovelId, NovelStatus, UserContext
from albedo_novels_infrastructure.auth import AuthenticationError
from .routes import ROUTES, Route


DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class HttpRequest:
    method: str
    path: str
    headers: Mapping[str, object] = field(default_factory=dict)
    query: Mapping[str, object] = field(default_factory=dict)
    path_params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: dict[str, Any]
    headers: Mapping[str, str] = field(default_factory=dict)


class HttpApplication:
    """Shared request dispatch, auth, pagination, and public JSON shaping."""

    def __init__(self, use_cases: NovelUseCases, authenticator: Authenticator) -> None:
        self._use_cases = use_cases
        self._authenticator = authenticator

    def handle(self, request: HttpRequest) -> HttpResponse:
        route = _find_route(request.method, request.path)
        if route is None:
            return self._planned_response(request)

        if route.auth_required:
            try:
                user = self._authenticator.authenticate(request.headers)
            except (AuthenticationError, ValueError) as error:
                return HttpResponse(
                    401,
                    {"error": "unauthorized", "message": str(error)},
                    {"WWW-Authenticate": "Bearer"},
                )

        if route.handler == "health":
            return HttpResponse(200, {"status": "ok", "service": "albedo-novel-service"})
        if route.handler == "list_novels":
            limit = _coerce_int(request.query.get("limit"), DEFAULT_LIMIT, maximum=MAX_LIMIT)
            offset = _coerce_int(request.query.get("offset"), 0, minimum=0)
            page = self._use_cases.list_novels(ListNovelsQuery(limit=limit, offset=offset))
            return HttpResponse(
                200,
                {
                    "items": [novel_to_dict(novel) for novel in page.items],
                    "total": page.total,
                    "limit": page.limit,
                    "offset": page.offset,
                },
            )
        if route.handler == "get_novel":
            novel_id_raw = request.path_params.get("novel_id") or _last_path_segment(request.path)
            try:
                novel = self._use_cases.get_novel(user, NovelId(str(novel_id_raw)))
            except NotFoundError as error:
                return HttpResponse(404, {"error": "not_found", "message": str(error)})
            except ForbiddenError as error:
                return HttpResponse(403, {"error": "forbidden", "message": str(error)})
            return HttpResponse(200, novel_to_dict(novel))
        return self._planned_response(request)

    @staticmethod
    def _planned_response(request: HttpRequest) -> HttpResponse:
        return HttpResponse(
            501,
            {
                "error": "not_implemented",
                "message": "Route is planned but not implemented yet.",
                "method": request.method,
                "path": request.path,
            },
        )


def _find_route(method: str, path: str) -> Route | None:
    for route in ROUTES:
        if route.method == method.upper() and _path_matches(route.path, path):
            return route
    return None


def _path_matches(pattern: str, path: str) -> bool:
    expression = re.sub(r"\{[^/]+\}", r"[^/]+", pattern)
    return re.fullmatch(expression, path) is not None


def _coerce_int(value: object, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
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


def novel_to_dict(novel: Novel) -> dict[str, Any]:
    return {
        "id": novel.id,
        "title": novel.title,
        "authorId": novel.author_id,
        "isbn": novel.isbn,
        "status": novel.status.value if isinstance(novel.status, NovelStatus) else str(novel.status),
        "createdAt": novel.created_at,
        "updatedAt": novel.updated_at,
    }

def _last_path_segment(path: str) -> str:
    return path.rsplit("/", 1)[-1]

