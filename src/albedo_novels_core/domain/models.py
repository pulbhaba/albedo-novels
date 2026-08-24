from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping, NewType


NovelId = NewType("NovelId", str)
UserId = NewType("UserId", str)


class NovelStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(frozen=True)
class UserContext:
    user_id: UserId
    roles: frozenset[str] = field(default_factory=frozenset)
    claims: Mapping[str, Any] = field(default_factory=dict)

    @property
    def can_publish(self) -> bool:
        return bool({"ROLE_EDITOR", "ROLE_ADMIN"} & self.roles)


@dataclass(frozen=True)
class Novel:
    id: NovelId
    title: str
    author_id: UserId
    status: NovelStatus
    created_at: str
    updated_at: str
    isbn: str | None = None
    last_modified_user_id: UserId | None = None

    def publish(self, updated_at: str, last_modified_user_id: UserId | None = None) -> "Novel":
        return replace(
            self,
            status=NovelStatus.PUBLISHED,
            updated_at=updated_at,
            last_modified_user_id=last_modified_user_id or self.last_modified_user_id,
        )

    def update_draft(
        self,
        *,
        title: str | None,
        isbn: str | None,
        updated_at: str,
        last_modified_user_id: UserId,
    ) -> "Novel":
        return replace(
            self,
            title=title if title is not None else self.title,
            isbn=isbn,
            updated_at=updated_at,
            last_modified_user_id=last_modified_user_id,
        )

    def is_readable_by(self, user: UserContext) -> bool:
        return (
            self.status == NovelStatus.PUBLISHED
            or self.author_id == user.user_id
            or user.can_publish
        )


@dataclass(frozen=True)
class LibraryEntry:
    user_id: UserId
    novel_id: NovelId
    created_at: str


@dataclass(frozen=True)
class LibraryNovel:
    """A readable novel together with the user's favorite metadata."""

    novel: Novel
    favorited_at: str
