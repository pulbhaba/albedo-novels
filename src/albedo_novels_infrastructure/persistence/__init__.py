"""Persistence adapters for the novel service."""

from albedo_novels_infrastructure.persistence.mysql import (
    MySqlLibraryRepository,
    MySqlNovelRepository,
)

__all__ = ["MySqlLibraryRepository", "MySqlNovelRepository"]
