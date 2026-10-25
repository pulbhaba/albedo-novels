"""Persistence adapters for the novel service."""

from albedo_novels_infrastructure.persistence.sqlalchemy import (
    Base, ChapterRow, LibraryEntryRow, NovelRow, SqlAlchemyChapterRepository, SqlAlchemyLibraryRepository, SqlAlchemyNovelRepository,
)
from albedo_novels_infrastructure.persistence.in_memory import (
    InMemoryChapterRepository, InMemoryLibraryRepository, InMemoryNovelRepository,
)

__all__ = [
    "Base",
    "ChapterRow",
    "InMemoryChapterRepository",
    "InMemoryLibraryRepository",
    "InMemoryNovelRepository",
    "LibraryEntryRow",
    "NovelRow",
    "SqlAlchemyLibraryRepository",
    "SqlAlchemyChapterRepository",
    "SqlAlchemyNovelRepository",
]
