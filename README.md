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
- `CORS_ALLOWED_ORIGINS` — comma-separated browser origins allowed by the local
  adapter and Lambda responses. Defaults to no allowed origins.

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

## CloudWatch logging and monitoring

The Lambda adapter emits one JSON log record when a request starts and one when
it completes. Records include the event name, method, path, status code,
duration, and (when supplied by the runtime) the Lambda request ID. Unexpected
exceptions produce a traceback record and a `request.failed` record before
being re-raised so the Lambda invocation still reports a failure.

The deployment role must include the standard `AWSLambdaBasicExecutionRole`
permissions (`logs:CreateLogGroup`, `logs:CreateLogStream`, and
`logs:PutLogEvents`). Configure a CloudWatch log group with an appropriate
retention period and add alarms or metric filters for `request.failed`, `ERROR`
records, and elevated 4xx/5xx rates in the service's infrastructure definition.

## Lambda Packaging

Build the deployable Lambda ZIP from the repository root:

```bash
./scripts/build_lambda.sh
```

The artifact is written to `dist/albedo-novels-lambda.zip`. It contains the
Lambda handler, the core and infrastructure packages, and the runtime
dependencies declared in `pyproject.toml`. Local-only FastAPI and Uvicorn
dependencies are not installed into the Lambda artifact. Set `PYTHON_BIN` to
choose the interpreter used for staging, for example
`PYTHON_BIN=.venv/bin/python ./scripts/build_lambda.sh`.

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
DAO data, including drafts, with `limit` and `offset` pagination. The
authenticated `GET /novels/{novelId}` endpoint returns a single novel when the
caller is allowed to read it (published novels for any reader, draft novels
for the owner or an editor/admin) and maps missing or forbidden novels to
`404` and `403` respectively. Other routes return the planned-route `501`
response until their core use cases are wired to persistence.
The authenticated `POST /novels` endpoint validates a title and optional ISBN,
creates a draft owned by the authenticated user, and returns the created novel.
The authenticated `PATCH /novels/{novelId}` endpoint updates the title and/or
ISBN of an owned draft. It returns `403` for another user's draft, `409` for a
published novel, and `400` when no editable field or an invalid value is sent.
The authenticated `POST /novels/{novelId}/publish` endpoint publishes a draft;
only users with `ROLE_EDITOR` or `ROLE_ADMIN` may use it. Publishing is
immediate; there is no submission or review queue in the current workflow. The
endpoint accepts drafts and returns the published novel with `200`; it returns
`401` without authentication, `403` for other roles, `404` when the novel does
not exist, and `409` when the novel is already published. The editor/admin
authorization is enforced in the core use case and applies equally to the
local and Lambda adapters.

### Publishing workflow

The service uses immediate publication after editorial authorization. Authors
create and edit drafts, then an editor or administrator publishes the draft in
one explicit action. A publish request is a one-way `draft` → `published`
transition; published novels cannot be republished or edited through the draft
update path. The API does not expose submission, review, approval, rejection,
or scheduled-publication states.

Frontend clients should show the publish action only for drafts and only to
users whose token includes `ROLE_EDITOR` or `ROLE_ADMIN`. After a successful
publish, clients should refresh or replace the novel with the returned
`status: "published"` representation and hide draft-edit and publish controls.
Clients should present `403` as an authorization error and `409` as a stale
state requiring a refresh. A future review workflow would require a separate
API and domain decision rather than changing the meaning of this endpoint.

The authenticated `PUT /library/{novelId}/favorite` endpoint adds a readable
novel to the current user's library. Repeating the request is idempotent and
returns the existing favorite. The local seeded composition keeps favorites in
memory; the MySQL composition uses the `library_entries` table. The authenticated
`GET /library` endpoint returns the current user's readable favorites as
`{"items":[{"novel": <novel representation>, "favoritedAt": <timestamp>}]}`.
Stale entries for deleted or no-longer-readable novels are omitted.
The authenticated `DELETE /library/{novelId}/favorite` endpoint removes the
favorite for the current user and returns `204 No Content`; repeating the
request is safe and returns the same response.

### Chapter metadata and content

Chapter navigation metadata is stored separately from chapter bodies. The
authenticated `GET /novels/{novelId}/chapters` endpoint returns
`{"items":[{"novelId":"...","chapterId":"...","title":"...","displayOrder":1}]}`
in ascending display order. The authenticated
`POST /novels/{novelId}/chapters` endpoint accepts `{"title":"..."}` and
returns the created chapter metadata with `201`; chapter IDs are stable and can
be passed to the content routes below. Titles must be non-empty strings of at
most 255 characters. Owners and editor/admin users can manage chapter
metadata; listing follows the novel's read permissions. Missing novels return
`404`, forbidden actions return `403`, and invalid titles return `400`.

Chapter bodies are kept behind a separate content storage port so they do not
become part of the chapter metadata model. The in-memory adapter supports local
development and tests; the Lambda composition stores immutable versions in S3.
It supports these authenticated routes:

- `GET /novels/{novelId}/chapters/{chapterId}` returns the latest version,
  including its `body`.
- `GET /novels/{novelId}/chapters/{chapterId}/versions` returns version
  metadata, newest first.
- `PUT /novels/{novelId}/chapters/{chapterId}` with `{"body": "..."}` creates
  the next immutable version and returns it.

Published chapter content is readable by any authenticated reader; draft
content is readable by its owner or an editor/admin. Owners and editor/admin
users may write content. S3 uses keys shaped like
`novels/{novelId}/chapters/{chapterId}/versions/{version}.json`. Each object
stores the body and author/timestamp metadata; the API response is unchanged.
The Lambda role needs `s3:PutObject` and `s3:GetObject` on
`arn:aws:s3:::BUCKET/novels/*`, plus `s3:ListBucket` on the bucket, restricted
to the `novels/*` prefix. No delete permission is required. If the bucket uses
a customer-managed KMS key, grant the Lambda role `kms:GenerateDataKey` for
writes and `kms:Decrypt` for reads, scoped to that key.

## SQLAlchemy persistence

Novel persistence stores lightweight metadata only. The `novels` table contains
the title, author ID, publication status, ISBN, timestamps, and last modifier;
the `chapters` table contains chapter IDs, titles, and display order. Chapter
bodies, covers, introductions, and full text belong in resource/content
storage. The schema is in
`src/albedo_novels_infrastructure/persistence/schema.sql`.
The baseline ER model and its auth-owned `users` boundary are documented in
[issue #35](https://github.com/pulbhaba/albedo-novels/issues/35); the SQLAlchemy
models in the same persistence package implement the `novels`,
`library_entries`, and `chapters` tables.

The Lambda runner uses `build_mysql_http_strategies()` to wire the novel,
library, and chapter metadata routes to SQLAlchemy repositories using
`NOVELS_DB_URL` (default:
`mysql+mysqlconnector://root:test_pass@localhost:3306/auth`). The local runner
uses the seeded novel data and in-memory metadata repositories. Chapter bodies
remain behind the separate content storage port. Lambda requires
`NOVELS_CHAPTER_CONTENT_BUCKET` to name an existing S3 bucket; the production
composition fails during initialization if the setting is missing or invalid.
Provision the bucket in deployment infrastructure, enable encryption and
public access blocking, and configure the Lambda execution role with the
permissions above. Local development continues to use in-memory chapter
content and does not require AWS credentials or this bucket setting.

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
