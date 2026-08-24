from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from albedo_novels_core.application import (
    CreateNovelCommand,
    ForbiddenError,
    ListNovelsQuery,
    NotFoundError,
    NovelUseCases,
)
from albedo_novels_core.application.ports import Authenticator
from albedo_novels_core.domain.models import LibraryEntry, LibraryNovel, Novel, NovelId, NovelStatus, UserContext, UserId
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
    body: object = None


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
        matched = _match_route(request.method, request.path)
        if matched is None:
            return self._planned_response(request)
        route, extracted_params = matched
        path_params = {**extracted_params, **request.path_params}

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
        if route.handler == "create_novel":
            command, error = _create_novel_command(request.body)
            if error is not None:
                return HttpResponse(400, {"error": "validation_error", "message": error})
            novel = self._use_cases.create_novel(
                user,
                CreateNovelCommand(title=command.title, author_id=user.user_id, isbn=command.isbn),
            )
            return HttpResponse(201, novel_to_dict(novel))
        if route.handler == "get_novel":
            novel_id_raw = path_params.get("novel_id") or _last_path_segment(request.path)
            try:
                novel = self._use_cases.get_novel(user, NovelId(str(novel_id_raw)))
            except NotFoundError as error:
                return HttpResponse(404, {"error": "not_found", "message": str(error)})
            except ForbiddenError as error:
                return HttpResponse(403, {"error": "forbidden", "message": str(error)})
            return HttpResponse(200, novel_to_dict(novel))
        if route.handler == "add_favorite":
            novel_id_raw = path_params.get("novel_id") or _last_path_segment(request.path)
            try:
                entry = self._use_cases.add_favorite(user, NovelId(str(novel_id_raw)))
            except NotFoundError as error:
                return HttpResponse(404, {"error": "not_found", "message": str(error)})
            except ForbiddenError as error:
                return HttpResponse(403, {"error": "forbidden", "message": str(error)})
            return HttpResponse(200, library_entry_to_dict(entry))
        if route.handler == "remove_favorite":
            novel_id_raw = path_params.get("novel_id") or _last_path_segment(request.path)
            self._use_cases.remove_favorite(user, NovelId(str(novel_id_raw)))
            return HttpResponse(204, {})
        if route.handler == "list_library":
            return HttpResponse(
                200,
                {"items": [library_novel_to_dict(item) for item in self._use_cases.list_library(user)]},
            )
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
    matched = _match_route(method, path)
    return matched[0] if matched is not None else None


def _match_route(method: str, path: str) -> tuple[Route, dict[str, str]] | None:
    for route in ROUTES:
        if route.method != method.upper():
            continue
        match = re.fullmatch(_route_pattern(route.path), path)
        if match is not None:
            return route, match.groupdict()
    return None


def _path_matches(pattern: str, path: str) -> bool:
    return re.fullmatch(_route_pattern(pattern), path) is not None


def _route_pattern(pattern: str) -> str:
    """Turn a route template into a safe regex with named path captures."""
    expression = re.escape(pattern)
    return re.sub(r"\\\{([^{}]+)\\\}", r"(?P<\1>[^/]+)", expression)


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


def _create_novel_command(body: object) -> tuple[CreateNovelCommand | None, str | None]:
    if not isinstance(body, Mapping):
        return None, "Request body must be a JSON object."

    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, "title is required and must be a non-empty string."
    if len(title) > 255:
        return None, "title must be 255 characters or fewer."

    isbn = body.get("isbn")
    if isbn is not None and (not isinstance(isbn, str) or not isbn.strip() or len(isbn) > 32):
        return None, "isbn must be a non-empty string of 32 characters or fewer."

    return CreateNovelCommand(title=title, author_id=UserId(""), isbn=isbn), None


def library_entry_to_dict(entry: LibraryEntry) -> dict[str, Any]:
    return {
        "novelId": entry.novel_id,
        "createdAt": entry.created_at,
    }


def library_novel_to_dict(item: LibraryNovel) -> dict[str, Any]:
    novel = item.novel
    return {
        "novel": novel_to_dict(novel),
        "favoritedAt": item.favorited_at,
    }


def _last_path_segment(path: str) -> str:
    return path.rsplit("/", 1)[-1]
