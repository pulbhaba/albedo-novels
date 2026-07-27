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

## Current Status

This first commit is repository setup and planning only. Feature implementation is tracked in
[`plan.md`](plan.md).
