# syntax=docker/dockerfile:1.6
# Local HTTP server for the Albedo novel service.
#
# The package is installed with the `local` extra so FastAPI and Uvicorn are
# available. The container is intentionally a single process with no hot-reload
# because it is consumed by docker compose as part of the shared local stack.

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build tooling and the package with the `local` extra so FastAPI and
# Uvicorn ship in the runtime image.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[local]"


FROM python:3.12-slim AS runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Copy the installed packages from the builder so we do not need build tooling
# in the runtime image.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/src /app/src

ENV PYTHONPATH=/app/src

EXPOSE 8000

# Use the local FastAPI/uvicorn entry point; compose overrides PORT if needed.
CMD ["python", "-m", "albedo_novels_local"]
