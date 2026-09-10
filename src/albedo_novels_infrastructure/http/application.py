from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from albedo_novels_core.application.ports import Authenticator
from albedo_novels_core.domain.models import UserContext
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


class RequestStrategy(Protocol):
    """Endpoint behavior selected by a route's handler name."""

    def handle(
        self,
        request: HttpRequest,
        user: UserContext | None,
        path_params: Mapping[str, str],
    ) -> HttpResponse:
        ...


class HttpApplication:
    """Coordinate route matching, authentication, and endpoint strategies."""

    def __init__(self, authenticator: Authenticator, strategies: Mapping[str, RequestStrategy]) -> None:
        self._authenticator = authenticator
        self._strategies = strategies

    def handle(self, request: HttpRequest) -> HttpResponse:
        matched = _match_route(request.method, request.path)
        if matched is None:
            return self._planned_response(request)
        route, extracted_params = matched
        path_params = {**extracted_params, **request.path_params}

        user = None
        if route.auth_required:
            try:
                user = self._authenticator.authenticate(request.headers)
            except (AuthenticationError, ValueError) as error:
                return HttpResponse(
                    401,
                    {"error": "unauthorized", "message": str(error)},
                    {"WWW-Authenticate": "Bearer"},
                )

        strategy = self._strategies.get(route.handler)
        if strategy is None:
            return self._planned_response(request)
        return strategy.handle(request, user, path_params)

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
