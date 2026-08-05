from __future__ import annotations

import json

import pytest
from starlette.requests import Request
from starlette.routing import Match

from albedo_novels_local import app as local_app


def request(path: str, headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [
            (name.lower().encode(), value.encode())
            for name, value in (headers or {}).items()
        ],
    }
    return Request(scope)


def test_health_route_returns_ok() -> None:
    assert local_app.health() == {
        "status": "ok",
        "service": "albedo-novel-service",
    }


def test_protected_route_requires_bearer_token() -> None:
    with pytest.raises(local_app.UnauthorizedError, match="bearer token"):
        local_app.current_user(request("/novels"))


def test_protected_route_returns_not_implemented_for_authenticated_user() -> None:
    response = local_app.planned_route(request("/novels"), object())

    assert response.status_code == 501
    assert json.loads(response.body)["error"] == "not_implemented"


def test_unknown_route_returns_not_found() -> None:
    match, _ = local_app.app.router.matches(request("/missing").scope)

    assert match is Match.NONE


def test_local_module_exposes_python_module_entrypoint() -> None:
    import importlib

    module = importlib.import_module("albedo_novels_local.__main__")

    assert callable(module.uvicorn.run)
