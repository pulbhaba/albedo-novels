"""Tests for the core listing use case against the in-memory seeded DAO."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from albedo_novels_core.application import (
    ListNovelsQuery,
    NovelUseCases,
)
from albedo_novels_infrastructure.persistence.seeded_novel_dao import (
    SeededNovelDao,
    SeededNovel,
)
from albedo_novels_core.domain.models import (
    Author,
    Novel,
    NovelId,
    NovelStatus,
    UserId,
)


class FixedClock:
    def __init__(self, value: str) -> None:
        self._value = value

    def utcnow_iso(self) -> str:
        return self._value


class FixedIds:
    def __init__(self, values: list[str]) -> None:
        self._values = list(values)

    def new_id(self) -> str:
        return self._values.pop(0)


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
        ids=FixedIds([str(uuid4()) for _ in range(8)]),
        clock=FixedClock("2026-08-07T00:00:00+00:00"),
    )


def test_list_novels_returns_seeded_books_paginated() -> None:
    use_cases = _use_cases()

    page = use_cases.list_novels(ListNovelsQuery(limit=2, offset=0))

    assert page.total == 4
    assert page.limit == 2
    assert page.offset == 0
    assert [novel.id for novel in page.items] == ["novel-004", "novel-003"]


def test_list_novels_respects_offset() -> None:
    use_cases = _use_cases()

    page = use_cases.list_novels(ListNovelsQuery(limit=2, offset=2))

    assert [novel.id for novel in page.items] == ["novel-002", "novel-001"]


def test_list_novels_uses_default_limit_when_zero_or_negative() -> None:
    use_cases = _use_cases()

    page = use_cases.list_novels(ListNovelsQuery(limit=0, offset=0))

    assert page.limit == 20
    assert page.total == 4
    assert len(page.items) == 4


def test_list_novels_clamps_oversized_limit() -> None:
    use_cases = _use_cases()

    page = use_cases.list_novels(ListNovelsQuery(limit=10_000, offset=0))

    assert page.limit == 100


def test_list_novels_negative_offset_normalises_to_zero() -> None:
    use_cases = _use_cases()

    page = use_cases.list_novels(ListNovelsQuery(limit=1, offset=-3))

    assert page.offset == 0
    assert page.items[0].id == "novel-004"


def test_seeded_dao_round_trips_save_and_get() -> None:
    dao = SeededNovelDao(seeds=())
    novel = Novel(
        id=NovelId("novel-xyz"),
        title="Untitled",
        author=Author(id=UserId("user-1"), display_name="User One"),
        cover_image_url="https://cdn.albedo.example/covers/untitled.jpg",
        status=NovelStatus.DRAFT,
        created_at=datetime.now(tz=timezone.utc).isoformat(),
        updated_at=datetime.now(tz=timezone.utc).isoformat(),
        owner_id=UserId("user-1"),
    )

    saved = dao.save(novel)

    assert saved.id == "novel-xyz"
    assert dao.get(NovelId("novel-xyz")) == novel
    assert dao.count_all() == 1


def test_seeded_dao_count_and_list_are_consistent() -> None:
    seeds = (
        SeededNovel(
            id="a",
            title="A",
            author_id="u",
            author_display_name="U",
            cover_image_url="",
            status=NovelStatus.DRAFT,
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
            owner_id="u",
        ),
        SeededNovel(
            id="b",
            title="B",
            author_id="u",
            author_display_name="U",
            cover_image_url="",
            status=NovelStatus.PUBLISHED,
            created_at="2026-02-01T00:00:00+00:00",
            updated_at="2026-02-01T00:00:00+00:00",
            owner_id="u",
        ),
    )

    dao = SeededNovelDao(seeds=seeds)

    assert dao.count_all() == 2
    assert [novel.id for novel in dao.list_all(limit=10, offset=0)] == ["b", "a"]
    assert dao.list_published()[0].id == "b"
    assert [novel.id for novel in dao.list_by_owner(UserId("u"))] == ["b", "a"]
