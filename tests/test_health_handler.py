from __future__ import annotations

import json
from typing import Any, Mapping
from unittest.mock import patch

import pytest

from albedo_novels_core.domain.models import UserContext, UserId

from albedo_novels_lambda.handler import lambda_handler


@pytest.fixture(autouse=True)
def auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ISSUER", "https://auth.example.test")
    monkeypatch.setenv("AUTH_AUDIENCE", "albedo-novel-service")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://auth.example.test/jwks")


def _event(method: str, path: str, headers: Mapping[str, str] | None = None, query: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "requestContext": {"http": {"method": method}},
        "rawPath": path,
        "headers": headers or {},
        "queryStringParameters": query,
    }


def test_health_route_returns_ok() -> None:
    response = lambda_handler(_event("GET", "/health"), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "status": "ok",
        "service": "albedo-novel-service",
    }


def test_unknown_route_is_not_implemented() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _event("POST", "/novels/42/publish", headers={"authorization": "Bearer access-token"}),
            None,
        )

    assert response["statusCode"] == 501
    body = json.loads(response["body"])
    assert body["error"] == "not_implemented"
    assert body["method"] == "POST"
    assert body["path"] == "/novels/42/publish"


def test_get_novels_returns_paginated_list_when_authenticated() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _event("GET", "/novels", headers={"authorization": "Bearer access-token"}, query={"limit": "2"}),
            None,
        )

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
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


def test_get_novels_returns_401_when_bearer_missing() -> None:
    response = lambda_handler(_event("GET", "/novels"), None)

    assert response["statusCode"] == 401
    assert json.loads(response["body"])["error"] == "unauthorized"


def test_planned_route_returns_401_when_bearer_missing() -> None:
    response = lambda_handler(_event("POST", "/novels/42/publish"), None)

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {
        "error": "unauthorized",
        "message": "A bearer token is required.",
    }


def test_get_novels_clamps_oversized_limit() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _event("GET", "/novels", headers={"authorization": "Bearer access-token"}, query={"limit": "1000"}),
            None,
        )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["limit"] == 100


def test_get_novel_returns_published_novel_payload_when_authenticated() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _event("GET", "/novels/novel-001", headers={"authorization": "Bearer access-token"}),
            None,
        )

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "novel-001"
    assert body["status"] == "published"
    assert body["authorId"] == "user-1"


def test_get_novel_returns_404_for_missing_novel() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _event("GET", "/novels/novel-missing", headers={"authorization": "Bearer access-token"}),
            None,
        )

    assert response["statusCode"] == 404
    assert json.loads(response["body"])["error"] == "not_found"


def test_get_novel_returns_401_when_bearer_missing() -> None:
    response = lambda_handler(_event("GET", "/novels/novel-001"), None)

    assert response["statusCode"] == 401
    assert json.loads(response["body"])["error"] == "unauthorized"


def test_add_favorite_returns_the_existing_entry_when_repeated() -> None:
    event = _event(
        "PUT",
        "/library/novel-001/favorite",
        headers={"authorization": "Bearer access-token"},
    )
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("lambda-favorite-reader")),
    ):
        first = lambda_handler(event, None)
        second = lambda_handler(event, None)

    assert first["statusCode"] == 200
    assert second["statusCode"] == 200
    assert json.loads(first["body"]) == json.loads(second["body"])
    assert json.loads(first["body"])["novelId"] == "novel-001"


def test_add_favorite_rejects_an_unreadable_draft() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("lambda-favorite-reader")),
    ):
        response = lambda_handler(
            _event(
                "PUT",
                "/library/novel-004/favorite",
                headers={"authorization": "Bearer access-token"},
            ),
            None,
        )

    assert response["statusCode"] == 403
    assert json.loads(response["body"])["error"] == "forbidden"


def test_list_library_returns_current_users_favorites() -> None:
    event = _event(
        "PUT",
        "/library/novel-002/favorite",
        headers={"authorization": "Bearer access-token"},
    )
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("lambda-library-reader")),
    ):
        lambda_handler(event, None)
        response = lambda_handler(
            _event("GET", "/library", headers={"authorization": "Bearer access-token"}),
            None,
        )

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["items"][0]["novel"]["id"] == "novel-002"
    assert body["items"][0]["novel"]["title"] == "A Map for Forgetting"
    assert body["items"][0]["favoritedAt"].startswith("2026-08-21T")


def test_list_library_returns_401_when_bearer_missing() -> None:
    response = lambda_handler(_event("GET", "/library"), None)

    assert response["statusCode"] == 401


def test_remove_favorite_is_idempotent_and_scoped_to_the_authenticated_user() -> None:
    favorite_event = _event(
        "PUT",
        "/library/novel-001/favorite",
        headers={"authorization": "Bearer access-token"},
    )
    remove_event = _event(
        "DELETE",
        "/library/novel-001/favorite",
        headers={"authorization": "Bearer access-token"},
    )
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("lambda-delete-reader")),
    ):
        lambda_handler(favorite_event, None)
        first = lambda_handler(remove_event, None)
        second = lambda_handler(remove_event, None)

    assert first["statusCode"] == 204
    assert second["statusCode"] == 204


def test_remove_favorite_requires_authentication() -> None:
    response = lambda_handler(_event("DELETE", "/library/novel-001/favorite"), None)

    assert response["statusCode"] == 401
