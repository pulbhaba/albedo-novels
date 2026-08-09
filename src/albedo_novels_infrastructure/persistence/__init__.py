"""Persistence adapters for the novel service."""

from albedo_novels_infrastructure.persistence.sqlalchemy import (
    Base, LibraryEntryRow, NovelRow, SqlAlchemyLibraryRepository, SqlAlchemyNovelRepository,
)

__all__ = ["Base", "LibraryEntryRow", "NovelRow", "SqlAlchemyLibraryRepository", "SqlAlchemyNovelRepository"]
