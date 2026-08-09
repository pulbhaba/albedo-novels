from __future__ import annotations

from typing import Mapping, Protocol

from albedo_novels_core.domain.models import UserContext


class Authenticator(Protocol):
    """Verify request credentials without coupling the core to a JWT library."""

    def authenticate(self, headers: Mapping[str, object]) -> UserContext:
        ...

from albedo_novels_core.domain.models import Novel, NovelId, UserId


class NovelRepository(Protocol):
    def save(self, novel: Novel) -> Novel:
        """Persist and return a novel."""

    def get(self, novel_id: NovelId) -> Novel | None:
        """Load a novel by ID."""

    def list_published(self) -> list[Novel]:
        """List published novels."""

    def list_by_author(self, author_id: UserId) -> list[Novel]:
        """List novels authored by one user."""

    def list_all(self, limit: int, offset: int) -> list[Novel]:
        """List novels regardless of status, paginated by limit/offset.

        Results are ordered deterministically (newest created first, then by
        stable id) so that a given offset always returns the same items.
        """

    def count_all(self) -> int:
        """Return the total number of novels regardless of status."""


class LibraryRepository(Protocol):
    def save(self, entry: object) -> object:
        """Persist and return a library entry."""

    def delete(self, user_id: UserId, novel_id: NovelId) -> None:
        """Remove one library entry if it exists."""

    def list_by_user(self, user_id: UserId) -> list[object]:
        """List library entries for one user."""


class IdGenerator(Protocol):
    def new_id(self) -> str:
        """Return a new unique identifier."""


class Clock(Protocol):
    def utcnow_iso(self) -> str:
        """Return the current UTC time in ISO-8601 format."""
