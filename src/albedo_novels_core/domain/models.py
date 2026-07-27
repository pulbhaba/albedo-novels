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
    owner_id: UserId
    title: str
    summary: str
    body: str
    status: NovelStatus
    created_at: str
    updated_at: str

    def publish(self, updated_at: str) -> Novel:
        return replace(self, status=NovelStatus.PUBLISHED, updated_at=updated_at)

    def is_readable_by(self, user: UserContext) -> bool:
        return self.status == NovelStatus.PUBLISHED or self.owner_id == user.user_id or user.can_publish


@dataclass(frozen=True)
class LibraryEntry:
    user_id: UserId
    novel_id: NovelId
    created_at: str
