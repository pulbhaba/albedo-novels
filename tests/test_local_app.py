from __future__ import annotations

import importlib
import json
from typing import Any, Mapping
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from albedo_novels_local import app as local_app


@pytest.fixture(autouse=True)
def auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ISSUER", "https://auth.example.test")
    monkeypatch.setenv("AUTH_AUDIENCE", "albedo-novel-service")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://auth.example.test/jwks")


def _build_event_headers() -> dict[str, str]:
    return {"authorization": "Bearer access-token"}


def test_health_route_returns_ok() -> None:
    assert local_app.health() == {
        "status": "ok",
        "service": "albedo-novel-service",
    }


def test_protected_route_requires_bearer_token() -> None:
    client = TestClient(local_app.app)

    response = client.get("/novels")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["error"] == "unauthorized"


def test_get_novels_returns_paginated_list_when_authenticated() -> None:
    client = TestClient(local_app.app)

    with patch(
        "albedo_novels_lambda.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = client.get(
            "/novels",
            params={"limit": 2, "offset": 0},
            headers=_build_event_headers(),
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
        "author",
        "coverImageUrl",
        "status",
        "createdAt",
        "updatedAt",
    }
    assert sample["author"] == {"id": "user-1", "displayName": "Asha Lindgren"}


def test_get_novels_uses_default_limit_when_query_missing() -> None:
    client = TestClient(local_app.app)

    with patch(
        "albedo_novels_lambda.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = client.get("/novels", headers=_build_event_headers())

    assert response.status_code == 200
    assert response.json()["limit"] == 20


def test_get_novels_rejects_negative_offset() -> None:
    client = TestClient(local_app.app)

    with patch(
        "albedo_novels_lambda.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = client.get(
            "/novels",
            params={"offset": -1},
            headers=_build_event_headers(),
        )

    assert response.status_code == 422


def test_unimplemented_routes_still_return_501() -> None:
    client = TestClient(local_app.app)

    with patch(
        "albedo_novels_lambda.auth.JwtVerifier.verify",
        return_value=object(),
    ):
        response = client.post("/novels", headers=_build_event_headers())

    assert response.status_code == 501
    body = response.json()
    assert body["error"] == "not_implemented"
    assert body["path"] == "/novels"
    assert body["method"] == "POST"


def test_local_module_exposes_python_module_entrypoint() -> None:
    module = importlib.import_module("albedo_novels_local.__main__")

    assert callable(module.uvicorn.run)
