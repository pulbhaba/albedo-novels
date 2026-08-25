from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


ALLOWED_METHODS = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
ALLOWED_HEADERS = "Authorization, Content-Type"


@dataclass(frozen=True)
class RuntimeConfig:
    auth_issuer: str
    auth_audience: str
    auth_jwks_url: str
    cors_allowed_origins: tuple[str, ...]

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "RuntimeConfig":
        values = os.environ if environment is None else environment
        required = {
            "AUTH_ISSUER": values.get("AUTH_ISSUER", "").strip(),
            "AUTH_AUDIENCE": values.get("AUTH_AUDIENCE", "").strip(),
            "AUTH_JWKS_URL": values.get("AUTH_JWKS_URL", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required authentication configuration: {', '.join(missing)}")

        origins = tuple(origin.strip() for origin in values.get("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip())
        return cls(
            auth_issuer=required["AUTH_ISSUER"],
            auth_audience=required["AUTH_AUDIENCE"],
            auth_jwks_url=required["AUTH_JWKS_URL"],
            cors_allowed_origins=origins,
        )


def cors_headers(request_headers: Mapping[str, object], config: RuntimeConfig | None = None) -> dict[str, str]:
    """Return CORS response headers only for configured request origins."""
    active_config = config or _cors_config()
    origin = next((value for key, value in request_headers.items() if key.lower() == "origin"), None)
    if not isinstance(origin, str) or origin not in active_config.cors_allowed_origins:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Vary": "Origin",
    }


def cors_preflight_headers(request_headers: Mapping[str, object], config: RuntimeConfig | None = None) -> dict[str, str]:
    """Return preflight headers only when the request origin is configured."""
    headers = cors_headers(request_headers, config)
    if not headers:
        return {}
    return {
        **headers,
        "Access-Control-Allow-Methods": ALLOWED_METHODS,
        "Access-Control-Allow-Headers": ALLOWED_HEADERS,
    }


def _cors_config() -> RuntimeConfig:
    """Read only the CORS setting for adapters that initialize before auth."""
    return RuntimeConfig(
        auth_issuer="",
        auth_audience="",
        auth_jwks_url="",
        cors_allowed_origins=tuple(
            origin.strip()
            for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        ),
    )


def cors_allowed_origins() -> tuple[str, ...]:
    return _cors_config().cors_allowed_origins
