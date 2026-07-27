from __future__ import annotations

from typing import Protocol

from albedo_novels_core.domain.models import LibraryEntry, Novel, NovelId, UserId


class NovelRepository(Protocol):
    def save(self, novel: Novel) -> Novel:
        """Persist and return a novel."""

    def get(self, novel_id: NovelId) -> Novel | None:
        """Load a novel by ID."""

    def list_published(self) -> list[Novel]:
        """List published novels."""

    def list_by_owner(self, owner_id: UserId) -> list[Novel]:
        """List novels owned by one user."""


class LibraryRepository(Protocol):
    def save(self, entry: LibraryEntry) -> LibraryEntry:
        """Persist and return a library entry."""

    def delete(self, user_id: UserId, novel_id: NovelId) -> None:
        """Remove one library entry if it exists."""

    def list_by_user(self, user_id: UserId) -> list[LibraryEntry]:
        """List library entries for one user."""


class IdGenerator(Protocol):
    def new_id(self) -> str:
        """Return a new unique identifier."""


class Clock(Protocol):
    def utcnow_iso(self) -> str:
        """Return the current UTC time in ISO-8601 format."""
