from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from albedo_novels_core.domain.models import UserContext
from albedo_novels_lambda.auth import AuthenticationError, JwtConfig, JwtVerifier, bearer_token


app = FastAPI(title="Albedo Novel Service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "albedo-novel-service"}


def current_user(request: Request) -> UserContext:
    try:
        token = bearer_token(request.headers)
        verifier = JwtVerifier(JwtConfig.from_environment())
        return verifier.verify(token)
    except AuthenticationError as error:
        raise UnauthorizedError(str(error)) from error


class UnauthorizedError(Exception):
    """Raised when a request does not contain a valid access token."""


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(_request: Request, error: UnauthorizedError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "message": str(error)},
        headers={"WWW-Authenticate": "Bearer"},
    )


def not_implemented(request: Request, _user: Annotated[UserContext, Depends(current_user)]) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": "not_implemented",
            "message": "Route is planned but not implemented yet.",
            "method": request.method,
            "path": request.url.path,
        },
    )


@app.post("/novels")
@app.get("/novels")
@app.get("/novels/{novel_id}")
@app.patch("/novels/{novel_id}")
@app.post("/novels/{novel_id}/publish")
@app.get("/library")
@app.put("/library/{novel_id}/favorite")
@app.delete("/library/{novel_id}/favorite")
def planned_route(
    request: Request,
    user: Annotated[UserContext, Depends(current_user)],
) -> JSONResponse:
    return not_implemented(request, user)
