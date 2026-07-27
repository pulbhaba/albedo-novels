from __future__ import annotations

import json

from albedo_novels_lambda.handler import lambda_handler


def test_health_route_returns_ok() -> None:
    response = lambda_handler(
        {
            "requestContext": {
                "http": {
                    "method": "GET",
                }
            },
            "rawPath": "/health",
        },
        None,
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "status": "ok",
        "service": "albedo-novel-service",
    }


def test_unknown_route_is_not_implemented() -> None:
    response = lambda_handler(
        {
            "requestContext": {
                "http": {
                    "method": "POST",
                }
            },
            "rawPath": "/novels",
        },
        None,
    )

    assert response["statusCode"] == 501
    assert json.loads(response["body"])["error"] == "not_implemented"
