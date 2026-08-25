from __future__ import annotations

import pytest
from jwt.exceptions import ExpiredSignatureError

from albedo_novels_infrastructure.auth import AuthenticationError, JwtConfig, JwtVerifier, bearer_token
from albedo_novels_infrastructure.config import RuntimeConfig


class FakeJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> object:
        assert token == "access-token"
        return type("SigningKey", (), {"key": "public-key"})()


def test_jwt_config_reads_required_environment_values() -> None:
    config = JwtConfig.from_environment(
        {
            "AUTH_ISSUER": "https://auth.example.test",
            "AUTH_AUDIENCE": "albedo-novel-service",
            "AUTH_JWKS_URL": "https://auth.example.test/jwks",
        }
    )

    assert config.audience == "albedo-novel-service"


def test_jwt_config_rejects_missing_values() -> None:
    with pytest.raises(ValueError, match="AUTH_AUDIENCE"):
        JwtConfig.from_environment({"AUTH_ISSUER": "issuer"})


def test_runtime_config_reads_adapter_environment_values() -> None:
    config = RuntimeConfig.from_environment(
        {
            "AUTH_ISSUER": "issuer",
            "AUTH_AUDIENCE": "audience",
            "AUTH_JWKS_URL": "https://auth.example.test/jwks",
            "CORS_ALLOWED_ORIGINS": "https://reader.example, https://editor.example",
        }
    )

    assert config.cors_allowed_origins == (
        "https://reader.example",
        "https://editor.example",
    )

def test_verifier_builds_user_context_from_valid_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    config = JwtConfig("issuer", "audience", "https://auth.example.test/jwks")

    def decode(token: str, key: str, **kwargs: object) -> dict[str, object]:
        assert token == "access-token"
        assert key == "public-key"
        assert kwargs["audience"] == "audience"
        assert kwargs["issuer"] == "issuer"
        return {"sub": "reader-1", "roles": ["ROLE_READER", "ROLE_EDITOR"]}

    monkeypatch.setattr("albedo_novels_infrastructure.auth.jwt.jwt.decode", decode)

    user = JwtVerifier(config, FakeJwksClient()).verify("access-token")

    assert user.user_id == "reader-1"
    assert user.roles == frozenset({"ROLE_READER", "ROLE_EDITOR"})


def test_verifier_maps_invalid_tokens_to_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    config = JwtConfig("issuer", "audience", "https://auth.example.test/jwks")

    def decode(*_args: object, **_kwargs: object) -> None:
        raise ExpiredSignatureError("expired")

    monkeypatch.setattr("albedo_novels_infrastructure.auth.jwt.jwt.decode", decode)

    with pytest.raises(AuthenticationError, match="invalid or expired"):
        JwtVerifier(config, FakeJwksClient()).verify("access-token")


def test_bearer_token_reads_case_insensitive_header() -> None:
    assert bearer_token({"authorization": "Bearer access-token"}) == "access-token"


def test_bearer_token_rejects_missing_header() -> None:
    with pytest.raises(AuthenticationError, match="bearer token"):
        bearer_token({})
