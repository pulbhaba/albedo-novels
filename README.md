# Albedo Novel Service

Python microservice for Albedo novel reading, writing, and library favorites.

This repository is designed as a hexagonal service with two Python packages:

- `albedo_novels_core`: domain models, ports, and application use cases.
- `albedo_novels_lambda`: AWS Lambda and API Gateway adapters.

The auth service remains the source of identity, JWT issuance, and role management.
This service should validate JWTs statelessly and authorize behavior from token claims.

## Lambda Entrypoint

Use this handler when wiring API Gateway to Lambda:

```text
albedo_novels_lambda.handler.lambda_handler
```

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### Running locally as a server

Install the local HTTP adapter and start it with Uvicorn:

```bash
pip install -e ".[local]"
uvicorn albedo_novels_local.app:app --reload --port 8000
```

The public `GET /health` endpoint returns the service health payload. Other
routes require a bearer token and currently return the planned-route `501`
response until their core use cases are wired to persistence.

For the shared MySQL, auth-api, and novels stack, run Compose from the
[`albedo-infrastructure`](https://github.com/pulbhaba/albedo-infrastructure)
repository. The local server uses `AUTH_ISSUER`, `AUTH_AUDIENCE`, and
`AUTH_JWKS_URL`; when auth-api runs in Compose, the JWKS URL is
`http://auth-api:8080/oauth2/jwks`.

## Authentication configuration

The Lambda adapter validates bearer tokens against the auth service's JWKS. Set
these values in the Lambda environment (or in the shell running it):

```text
AUTH_ISSUER=https://auth.example.com
AUTH_AUDIENCE=albedo-novel-service
AUTH_JWKS_URL=https://auth.example.com/.well-known/jwks.json
```

Tokens must contain `sub` and `roles` claims. The adapter accepts a roles array
or a whitespace/comma-separated roles string and exposes the normalized roles to
the framework-free core layer.

## Current Status

The local HTTP adapter and JWT authentication foundation are implemented. Novel persistence and
the remaining use cases are tracked in [`plan.md`](plan.md).
