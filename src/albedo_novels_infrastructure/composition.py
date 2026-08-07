from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from albedo_novels_core.application import NovelUseCases
from albedo_novels_infrastructure.persistence.seeded_novel_dao import dao_test


def build_use_cases() -> NovelUseCases:
    return NovelUseCases(
        novels=dao_test(),
        library=EmptyLibraryRepository(),
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


class EmptyLibraryRepository:
    """Stand-in until the MySQL library adapter lands (issue #13)."""

    def save(self, entry: object) -> object:
        return entry

    def delete(self, _user_id: object, _novel_id: object) -> None:
        return None

    def list_by_user(self, _user_id: object) -> list[object]:
        return []


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class SystemClock:
    def utcnow_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()
