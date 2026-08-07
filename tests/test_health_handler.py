from __future__ import annotations

import json
from typing import Any, Mapping
from unittest.mock import patch

import pytest

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
        "author",
        "coverImageUrl",
        "status",
        "createdAt",
        "updatedAt",
    }
    assert sample["author"] == {"id": "user-1", "displayName": "Asha Lindgren"}


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
