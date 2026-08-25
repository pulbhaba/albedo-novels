from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from albedo_novels_core.domain.models import UserContext, UserId
from albedo_novels_infrastructure.auth import AuthenticationError
from albedo_novels_lambda.handler import lambda_handler


@pytest.fixture(autouse=True)
def auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ISSUER", "https://auth.example.test")
    monkeypatch.setenv("AUTH_AUDIENCE", "albedo-novel-service")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://auth.example.test/jwks")


def _v2_event(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "requestContext": {"http": {"method": method}},
        "rawPath": path,
        "headers": headers or {},
        "queryStringParameters": query,
        "body": json.dumps(body) if body is not None else None,
    }


def _v1_event(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "httpMethod": method,
        "path": path,
        "headers": headers or {},
        "queryStringParameters": query,
    }


def test_lambda_maps_api_gateway_v1_event_to_paginated_json_response() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _v1_event(
                "GET",
                "/novels",
                headers={"Authorization": "Bearer access-token"},
                query={"limit": "1", "offset": "1"},
            ),
            None,
        )

    assert response["statusCode"] == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    assert json.loads(response["body"]) == {
        "items": [
            {
                "id": "novel-003",
                "title": "Saltwater Letters",
                "authorId": "user-3",
                "isbn": "978-000000003",
                "status": "published",
                "createdAt": "2026-03-01T07:00:00+00:00",
                "updatedAt": "2026-03-01T07:00:00+00:00",
            }
        ],
        "total": 4,
        "limit": 1,
        "offset": 1,
    }


def test_lambda_adds_cors_headers_for_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://reader.example")
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _v2_event(
                "GET",
                "/novels",
                headers={
                    "authorization": "Bearer access-token",
                    "origin": "https://reader.example",
                },
            ),
            None,
        )

    assert response["headers"]["Access-Control-Allow-Origin"] == "https://reader.example"
    assert response["headers"]["Vary"] == "Origin"


def test_lambda_maps_invalid_pagination_to_safe_defaults() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = lambda_handler(
            _v2_event(
                "GET",
                "/novels",
                headers={"authorization": "Bearer access-token"},
                query={"limit": "not-a-number", "offset": "-4"},
            ),
            None,
        )

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_lambda_maps_invalid_bearer_token_to_unauthorized_response() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        side_effect=AuthenticationError("Access token is invalid or expired."),
    ):
        response = lambda_handler(
            _v2_event(
                "GET",
                "/novels",
                headers={"authorization": "Bearer expired-token"},
            ),
            None,
        )

    assert response == {
        "statusCode": 401,
        "headers": {
            "Content-Type": "application/json",
            "WWW-Authenticate": "Bearer",
        },
        "body": json.dumps(
            {
                "error": "unauthorized",
                "message": "Access token is invalid or expired.",
            }
        ),
    }


def test_lambda_creates_owned_draft() -> None:
    with patch(
        "albedo_novels_infrastructure.auth.JwtVerifier.verify",
        return_value=UserContext(UserId("creator-1")),
    ):
        response = lambda_handler(
            _v2_event(
                "POST",
                "/novels",
                headers={"authorization": "Bearer access-token"},
                body={"title": "A New Novel", "isbn": "978-000000099"},
            ),
            None,
        )

    assert response["statusCode"] == 201
    assert response["headers"]["Content-Type"] == "application/json"
    body = json.loads(response["body"])
    assert body["title"] == "A New Novel"
    assert body["authorId"] == "creator-1"
    assert body["status"] == "draft"
