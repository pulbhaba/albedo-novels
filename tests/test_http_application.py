from __future__ import annotations

from albedo_novels_infrastructure.http.application import (
    HttpApplication,
    HttpRequest,
    HttpResponse,
    _find_route,
    _match_route,
)


class _Authenticator:
    def authenticate(self, headers: object) -> None:
        return None


class _Strategy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def handle(self, request: HttpRequest, user: object | None, path_params: dict[str, str]) -> HttpResponse:
        self.calls.append((request.path, path_params))
        return HttpResponse(299, {"handled": True})


def test_application_dispatches_to_strategy_selected_by_route_handler() -> None:
    strategy = _Strategy()
    application = HttpApplication(_Authenticator(), {"get_novel": strategy})

    response = application.handle(HttpRequest("GET", "/novels/novel-123"))

    assert response == HttpResponse(299, {"handled": True})
    assert strategy.calls == [("/novels/novel-123", {"novel_id": "novel-123"})]


def test_application_keeps_unregistered_routes_planned() -> None:
    application = HttpApplication(_Authenticator(), {})

    response = application.handle(HttpRequest("GET", "/novels/novel-123"))

    assert response.status_code == 501
    assert response.body["error"] == "not_implemented"


def test_route_matching_extracts_named_parameter_from_suffixed_path() -> None:
    matched = _match_route("POST", "/novels/novel-123/publish")

    assert matched is not None
    route, path_params = matched
    assert route.handler == "publish_novel"
    assert path_params == {"novel_id": "novel-123"}


def test_route_lookup_remains_compatible_with_route_only_callers() -> None:
    route = _find_route("GET", "/health")

    assert route is not None
    assert route.handler == "health"


def test_draft_update_route_is_declared_in_shared_route_table() -> None:
    matched = _match_route("PATCH", "/novels/novel-123")

    assert matched is not None
    route, path_params = matched
    assert route.handler == "update_draft"
    assert path_params == {"novel_id": "novel-123"}
