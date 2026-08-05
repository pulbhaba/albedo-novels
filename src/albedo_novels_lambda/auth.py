from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from albedo_novels_core.domain.models import UserContext, UserId


class AuthenticationError(Exception):
    """Raised when a bearer token cannot identify an authenticated user."""


@dataclass(frozen=True)
class JwtConfig:
    issuer: str
    audience: str
    jwks_url: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "JwtConfig":
        values = os.environ if environment is None else environment
        required = {
            "AUTH_ISSUER": values.get("AUTH_ISSUER", "").strip(),
            "AUTH_AUDIENCE": values.get("AUTH_AUDIENCE", "").strip(),
            "AUTH_JWKS_URL": values.get("AUTH_JWKS_URL", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required authentication configuration: {', '.join(missing)}")

        return cls(
            issuer=required["AUTH_ISSUER"],
            audience=required["AUTH_AUDIENCE"],
            jwks_url=required["AUTH_JWKS_URL"],
        )


class JwtVerifier:
    def __init__(self, config: JwtConfig, jwks_client: Any | None = None) -> None:
        self._config = config
        self._jwks_client = jwks_client or PyJWKClient(config.jwks_url)

    def verify(self, token: str) -> UserContext:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iss", "aud", "sub", "roles"]},
            )
        except (PyJWTError, ValueError, TypeError) as error:
            raise AuthenticationError("Access token is invalid or expired.") from error

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Access token is missing a valid subject.")

        return UserContext(
            user_id=UserId(subject),
            roles=_normalize_roles(claims.get("roles")),
            claims=claims,
        )


def bearer_token(headers: Mapping[str, Any] | None) -> str:
    authorization = next(
        (value for key, value in (headers or {}).items() if key.lower() == "authorization"),
        None,
    )
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise AuthenticationError("A bearer token is required.")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthenticationError("A bearer token is required.")
    return token


def _normalize_roles(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        roles = [role for role in value.replace(",", " ").split() if role]
    elif isinstance(value, list) and all(isinstance(role, str) and role for role in value):
        roles = value
    else:
        raise AuthenticationError("Access token contains invalid roles.")

    return frozenset(roles)
