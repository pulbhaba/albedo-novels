from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from albedo_novels_infrastructure.auth import JwtAuthenticator
from albedo_novels_infrastructure.composition import build_use_cases
from albedo_novels_infrastructure.http import HttpApplication, HttpRequest, ROUTES, Route


app = FastAPI(title="Albedo Novel Service")


def _application() -> HttpApplication:
    return HttpApplication(build_use_cases(), JwtAuthenticator())


def _endpoint(route: Route):
    async def handle(request: Request) -> JSONResponse:
        shared_request = HttpRequest(
            method=route.method,
            path=request.url.path,
            headers=dict(request.headers),
            query=dict(request.query_params),
            path_params=dict(request.path_params),
        )
        response = _application().handle(shared_request)
        return JSONResponse(status_code=response.status_code, content=response.body, headers=dict(response.headers))

    return handle


# Route registration is adapter glue only. Endpoint behavior and auth remain
# in albedo_novels_infrastructure.http.HttpApplication.
for _route in ROUTES:
    app.add_api_route(_route.path, _endpoint(_route), methods=[_route.method])
