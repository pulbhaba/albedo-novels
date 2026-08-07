"""Domain layer for the Albedo novel service.

Exposes the framework-free value objects, entities, and helpers used by the
application layer.
"""
from __future__ import annotations

from albedo_novels_core.domain.models import (
    Author,
    LibraryEntry,
    Novel,
    NovelId,
    NovelStatus,
    UserContext,
    UserId,
)

__all__ = [
    "Author",
    "LibraryEntry",
    "Novel",
    "NovelId",
    "NovelStatus",
    "UserContext",
    "UserId",
]
