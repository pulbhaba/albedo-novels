"""Persistence adapters for the novel service."""

from albedo_novels_infrastructure.persistence.sqlalchemy import (
    Base, LibraryEntryRow, NovelRow, SqlAlchemyLibraryRepository, SqlAlchemyNovelRepository,
)
from albedo_novels_infrastructure.persistence.in_memory import (
    InMemoryLibraryRepository, InMemoryNovelRepository,
)

__all__ = [
    "Base",
    "InMemoryLibraryRepository",
    "InMemoryNovelRepository",
    "LibraryEntryRow",
    "NovelRow",
    "SqlAlchemyLibraryRepository",
    "SqlAlchemyNovelRepository",
]
