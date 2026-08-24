from __future__ import annotations

import asyncio
import importlib
import json
from typing import Any, Mapping
from urllib.parse import urlencode
from unittest.mock import patch

import pytest

from albedo_novels_core.domain.models import UserContext, UserId

from albedo_novels_local import app as local_app


@pytest.fixture(autouse=True)
def auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ISSUER", "https://auth.example.test")
    monkeypatch.setenv("AUTH_AUDIENCE", "albedo-novel-service")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://auth.example.test/jwks")


def _build_event_headers() -> dict[str, str]:
    return {"authorization": "Bearer access-token"}


class _Response:
    def __init__(self, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers

    def json(self) -> Any:
        return json.loads(self._body)


def _request(method: str, path: str, *, headers: Mapping[str, str] | None = None, params: Mapping[str, object] | None = None, body: Mapping[str, object] | None = None) -> _Response:
    query = urlencode(params or {})
    request_body = json.dumps(body or {}).encode() if body is not None else b""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 1234),
        "root_path": "",
        "http_version": "1.1",
    }

    async def send_request() -> _Response:
        response_status = 500
        response_headers: dict[str, str] = {}
        response_body = b""

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": request_body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            nonlocal response_status, response_headers, response_body
            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = {key.decode(): value.decode() for key, value in message["headers"]}
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")

        await local_app.app(scope, receive, send)
        return _Response(response_status, response_body, response_headers)

    return asyncio.run(send_request())


def test_health_route_returns_ok() -> None:
    response = _request("GET", "/health")

    assert response.json() == {
        "status": "ok",
        "service": "albedo-novel-service",
    }


def test_protected_route_requires_bearer_token() -> None:
    response = _request("GET", "/novels")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["error"] == "unauthorized"


def test_get_novels_returns_paginated_list_when_authenticated() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = _request(
            "GET",
            "/novels",
            headers=_build_event_headers(),
            params={"limit": 2, "offset": 0},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == ["novel-004", "novel-003"]
    sample = body["items"][0]
    assert set(sample.keys()) == {
        "id",
        "title",
        "authorId",
        "isbn",
        "status",
        "createdAt",
        "updatedAt",
    }
    assert sample["authorId"] == "user-1"


def test_get_novels_uses_default_limit_when_query_missing() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = _request("GET", "/novels", headers=_build_event_headers())

    assert response.status_code == 200
    assert response.json()["limit"] == 20


def test_get_novels_rejects_negative_offset() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = _request(
            "GET",
            "/novels",
            headers=_build_event_headers(),
            params={"offset": -1},
        )

    assert response.status_code == 200
    assert response.json()["offset"] == 0


def test_create_novel_returns_owned_draft() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("creator-1")),
    ):
        response = _request("POST", "/novels", headers=_build_event_headers(), body={"title": "A New Novel", "isbn": "978-000000099"})

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "A New Novel"
    assert body["authorId"] == "creator-1"
    assert body["isbn"] == "978-000000099"
    assert body["status"] == "draft"


def test_create_novel_rejects_invalid_body() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("creator-1")),
    ):
        response = _request("POST", "/novels", headers=_build_event_headers(), body={"title": ""})

    assert response.status_code == 400
    assert response.json()["error"] == "validation_error"


def test_planned_route_auth_failure_matches_lambda_semantics() -> None:
    response = _request("POST", "/novels/42/publish")

    assert response.status_code == 401
    assert response.json() == {
        "error": "unauthorized",
        "message": "A bearer token is required.",
    }


def test_local_module_exposes_python_module_entrypoint() -> None:
    module = importlib.import_module("albedo_novels_local.__main__")

    assert callable(module.uvicorn.run)


def test_get_novel_returns_published_novel_payload_when_authenticated() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = _request(
            "GET",
            "/novels/novel-001",
            headers=_build_event_headers(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "novel-001"
    assert body["status"] == "published"
    assert body["authorId"] == "user-1"


def test_get_novel_returns_404_for_missing_novel() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = _request(
            "GET",
            "/novels/novel-missing",
            headers=_build_event_headers(),
        )

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_get_novel_returns_401_when_bearer_missing() -> None:
    response = _request("GET", "/novels/novel-001")

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_add_favorite_is_idempotent_for_a_readable_novel() -> None:
    user = UserContext(UserId("local-favorite-reader"))
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=user,
    ):
        first = _request(
            "PUT",
            "/library/novel-001/favorite",
            headers=_build_event_headers(),
        )
        second = _request(
            "PUT",
            "/library/novel-001/favorite",
            headers=_build_event_headers(),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["novelId"] == "novel-001"


def test_add_favorite_rejects_an_unreadable_draft() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("local-favorite-reader")),
    ):
        response = _request(
            "PUT",
            "/library/novel-004/favorite",
            headers=_build_event_headers(),
        )

    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_list_library_returns_only_current_users_readable_favorites() -> None:
    user = UserContext(UserId("local-library-reader"))
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=user,
    ):
        _request("PUT", "/library/novel-001/favorite", headers=_build_event_headers())
        response = _request("GET", "/library", headers=_build_event_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["novel"] == {
        "id": "novel-001",
        "title": "The Glass Compass",
        "authorId": "user-1",
        "isbn": "978-000000001",
        "status": "published",
        "createdAt": "2026-01-04T09:30:00+00:00",
        "updatedAt": "2026-01-12T12:15:00+00:00",
    }
    assert body["items"][0]["favoritedAt"].startswith("2026-08-21T")


def test_list_library_requires_authentication() -> None:
    response = _request("GET", "/library")

    assert response.status_code == 401


def test_remove_favorite_is_idempotent() -> None:
    user = UserContext(UserId("local-delete-reader"))
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=user,
    ):
        _request("PUT", "/library/novel-001/favorite", headers=_build_event_headers())
        first = _request("DELETE", "/library/novel-001/favorite", headers=_build_event_headers())
        second = _request("DELETE", "/library/novel-001/favorite", headers=_build_event_headers())

    assert first.status_code == 204
    assert second.status_code == 204


def test_remove_favorite_requires_authentication() -> None:
    response = _request("DELETE", "/library/novel-001/favorite")

    assert response.status_code == 401
