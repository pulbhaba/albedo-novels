# Albedo Novel Service

Python microservice for Albedo novel reading, writing, and library favorites.

This repository is designed as a hexagonal service with two Python packages:

- `albedo_novels_core`: domain models, ports, and application use cases.
- `albedo_novels_lambda`: AWS Lambda and API Gateway adapters.

The auth service remains the source of identity, JWT issuance, and role management.
This service should validate JWTs statelessly and authorize behavior from token claims.


## Local Development (Docker Compose stack)

The shared local stack (MySQL + auth-api + novels-api) lives in the
[`albedo-infrastructure`](https://github.com/pulbhaba/albedo-infrastructure)
repository. From a full workspace checkout produced by `repo sync` against
`albedo-manifest`, run:

```bash
cd infrastructure
cp .env.example .env
docker compose up --build
```

The novels-api service is built from `../backend/novels` using the
`Dockerfile` in this repository. The container installs the `local` extra
(FastAPI + Uvicorn) and runs `python -m albedo_novels_local`, which exposes
the FastAPI app on port `8000`.

The novels container reads the following environment variables (defaults are
suitable for the local stack and are pre-populated in
`albedo-infrastructure/.env.example`):

- `HOST` / `PORT` — bind address for the local HTTP server (Compose sets
  `PORT=8000`).
- `AUTH_ISSUER` — issuer claim expected on incoming access tokens. Defaults
  to `http://auth-api:8080` for the in-stack auth service.
- `AUTH_AUDIENCE` — audience claim expected on incoming access tokens.
  Defaults to `albedo-novel-service`.
- `AUTH_JWKS_URL` — JWKS endpoint used to verify token signatures. Defaults
  to `http://auth-api:8080/oauth2/jwks`, the in-stack auth-api endpoint.

Override any of these in `infrastructure/.env` to point the novels service at
an external auth deployment.

Once the stack is up, the local health endpoint mirrors the Lambda adapter:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"albedo-novel-service"}
```

The `tests/test_local_app.py` and `tests/test_health_handler.py` suites
assert that the local server returns the same `/health` payload shape as the
Lambda handler.

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

The public `GET /health` endpoint returns the service health payload. The
authenticated `GET /novels` endpoint currently serves the deterministic seeded
DAO data, including drafts, with `limit` and `offset` pagination. Other routes
return the planned-route `501` response until their core use cases are wired to
persistence.

## MySQL persistence

Novel persistence stores metadata only; novel chapters and other content are
separate from the `novels` table. The schema for `novels` and
`library_entries` is in `src/albedo_novels_infrastructure/persistence/schema.sql`.
Apply it to the configured database before using `build_mysql_use_cases()`.

The MySQL adapter reads `NOVELS_DB_HOST`, `NOVELS_DB_PORT`, `NOVELS_DB_NAME`,
`NOVELS_DB_USER`, and `NOVELS_DB_PASSWORD` (defaulting to the local Compose
MySQL values). It implements the core `NovelRepository` and
`LibraryRepository` ports; the core package does not import the MySQL driver.

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
