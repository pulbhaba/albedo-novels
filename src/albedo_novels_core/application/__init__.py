"""Application layer: use cases and ports.

This package must not import any third-party SDK. It only depends on the
domain layer and the Python standard library.
"""
from __future__ import annotations

from albedo_novels_core.application.ports import (
    Clock,
    IdGenerator,
    LibraryRepository,
    NovelRepository,
)
from albedo_novels_core.application.use_cases import (
    CreateNovelCommand,
    DEFAULT_LIST_LIMIT,
    ForbiddenError,
    ListNovelsQuery,
    MAX_LIST_LIMIT,
    NotFoundError,
    NovelListPage,
    NovelUseCases,
)

__all__ = [
    "Clock",
    "CreateNovelCommand",
    "DEFAULT_LIST_LIMIT",
    "ForbiddenError",
    "IdGenerator",
    "LibraryRepository",
    "ListNovelsQuery",
    "MAX_LIST_LIMIT",
    "NotFoundError",
    "NovelListPage",
    "NovelRepository",
    "NovelUseCases",
]
