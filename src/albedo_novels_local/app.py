from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from albedo_novels_core.application import ListNovelsQuery, NovelUseCases
from albedo_novels_core.domain.models import Novel, NovelStatus
from albedo_novels_infrastructure.persistence.seeded_novel_dao import dao_test
from albedo_novels_lambda.auth import (
    AuthenticationError,
    JwtConfig,
    JwtVerifier,
    bearer_token,
)


app = FastAPI(title="Albedo Novel Service")


# --- Health -----------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "albedo-novel-service"}


# --- Auth wiring ------------------------------------------------------------


class UnauthorizedError(Exception):
    """Raised when a request does not contain a valid access token."""


def current_user(request: Request) -> str:
    try:
        token = bearer_token(request.headers)
        verifier = JwtVerifier(JwtConfig.from_environment())
        verifier.verify(token)
    except (AuthenticationError, ValueError) as error:
        raise UnauthorizedError(str(error)) from error
    # The list endpoint only needs a verified caller. The richer UserContext
    # is reserved for the per-author and library endpoints.
    return "authenticated"


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(_request: Request, error: UnauthorizedError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "message": str(error)},
        headers={"WWW-Authenticate": "Bearer"},
    )


# --- Public listing endpoint ------------------------------------------------


@app.get("/novels")
def list_novels(
    limit: int = Query(default=20, ge=0, le=100),
    offset: int = Query(default=0, ge=0),
    _user: Annotated[str, Depends(current_user)] = ...,
) -> dict[str, object]:
    use_cases = _build_use_cases()
    page = use_cases.list_novels(ListNovelsQuery(limit=limit, offset=offset))
    return {
        "items": [novel_to_dict(novel) for novel in page.items],
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
    }


# --- Not-implemented placeholders ------------------------------------------


@app.post("/novels")
@app.get("/novels/{novel_id}")
@app.patch("/novels/{novel_id}")
@app.post("/novels/{novel_id}/publish")
@app.get("/library")
@app.put("/library/{novel_id}/favorite")
@app.delete("/library/{novel_id}/favorite")
def planned_route(
    request: Request,
    _user: Annotated[str, Depends(current_user)],
) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": "not_implemented",
            "message": "Route is planned but not implemented yet.",
            "method": request.method,
            "path": request.url.path,
        },
    )


# --- Composition helpers ----------------------------------------------------


def _build_use_cases() -> NovelUseCases:
    return NovelUseCases(
        novels=dao_test(),
        library=EmptyLibraryRepository(),
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


class EmptyLibraryRepository:
    """Stand-in until the MySQL library adapter lands (issue #13)."""

    def save(self, entry: object) -> object:
        return entry

    def delete(self, _user_id: object, _novel_id: object) -> None:
        return None

    def list_by_user(self, _user_id: object) -> list[object]:
        return []


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class SystemClock:
    def utcnow_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()


def novel_to_dict(novel: Novel) -> dict[str, object]:
    """Serialise a Novel domain object to the public JSON shape."""
    return {
        "id": novel.id,
        "title": novel.title,
        "author": {
            "id": novel.author.id,
            "displayName": novel.author.display_name,
        },
        "coverImageUrl": novel.cover_image_url,
        "status": novel.status.value if isinstance(novel.status, NovelStatus) else str(novel.status),
        "createdAt": novel.created_at,
        "updatedAt": novel.updated_at,
    }
