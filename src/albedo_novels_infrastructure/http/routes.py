from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Method = Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
RouteHandler = str


@dataclass(frozen=True)
class Route:
    method: Method
    path: str
    handler: RouteHandler
    auth_required: bool


# This is the only place where the public HTTP surface is declared. Adapters
# iterate this table; they do not implement endpoint behavior themselves.
ROUTES: tuple[Route, ...] = (
    Route("GET", "/health", "health", False),
    Route("GET", "/novels", "list_novels", True),
    Route("POST", "/novels", "planned", True),
    Route("GET", "/novels/{novel_id}", "get_novel", True),
    Route("PATCH", "/novels/{novel_id}", "planned", True),
    Route("POST", "/novels/{novel_id}/publish", "planned", True),
    Route("GET", "/library", "list_library", True),
    Route("PUT", "/library/{novel_id}/favorite", "add_favorite", True),
    Route("DELETE", "/library/{novel_id}/favorite", "remove_favorite", True),
)
