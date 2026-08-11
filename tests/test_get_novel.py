"""Tests for the framework-free get_novel use case against the seeded DAO."""
from __future__ import annotations

from albedo_novels_core.application import (
    ForbiddenError,
    NotFoundError,
    NovelUseCases,
)
from albedo_novels_core.domain.models import (
    NovelId,
    UserContext,
    UserId,
)
from albedo_novels_infrastructure.persistence.seeded_novel_dao import SeededNovelDao


class EmptyLibraryRepository:
    def save(self, entry: object) -> object:
        return entry

    def delete(self, _user_id: object, _novel_id: object) -> None:
        return None

    def list_by_user(self, _user_id: object) -> list[object]:
        return []


def _use_cases() -> NovelUseCases:
    return NovelUseCases(
        novels=SeededNovelDao(),
        library=EmptyLibraryRepository(),
        ids=type("Ids", (), {"new_id": staticmethod(lambda: "unused")})(),
        clock=type("Clock", (), {"utcnow_iso": staticmethod(lambda: "2026-08-11T00:00:00+00:00")})(),
    )


def test_get_novel_returns_published_novel_for_reader() -> None:
    use_cases = _use_cases()
    reader = UserContext(user_id=UserId("reader-1"))

    novel = use_cases.get_novel(reader, NovelId("novel-001"))

    assert novel.id == "novel-001"
    assert novel.title == "The Glass Compass"
    assert novel.status.value == "published"


def test_get_novel_returns_draft_novel_for_owner() -> None:
    use_cases = _use_cases()
    owner = UserContext(user_id=UserId("user-1"))

    novel = use_cases.get_novel(owner, NovelId("novel-004"))

    assert novel.id == "novel-004"
    assert novel.status.value == "draft"


def test_get_novel_raises_forbidden_when_reader_reads_draft() -> None:
    use_cases = _use_cases()
    reader = UserContext(user_id=UserId("reader-9"))

    import pytest
    with pytest.raises(ForbiddenError):
        use_cases.get_novel(reader, NovelId("novel-004"))


def test_get_novel_raises_not_found_for_missing_id() -> None:
    use_cases = _use_cases()
    reader = UserContext(user_id=UserId("reader-1"))

    import pytest
    with pytest.raises(NotFoundError):
        use_cases.get_novel(reader, NovelId("novel-missing"))
