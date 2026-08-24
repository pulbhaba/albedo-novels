from __future__ import annotations

from albedo_novels_infrastructure.http.application import _find_route, _match_route


def test_route_matching_extracts_named_parameter_from_suffixed_path() -> None:
    matched = _match_route("POST", "/novels/novel-123/publish")

    assert matched is not None
    route, path_params = matched
    assert route.handler == "planned"
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
