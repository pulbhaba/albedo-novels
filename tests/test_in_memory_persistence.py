"""Contract tests for the in-memory persistence adapters."""
from __future__ import annotations

from albedo_novels_core.domain.models import LibraryEntry, Novel, NovelId, NovelStatus, UserId
from albedo_novels_infrastructure.persistence.in_memory import (
    InMemoryLibraryRepository,
    InMemoryNovelRepository,
)


def _novel(
    novel_id: str,
    created_at: str,
    *,
    author_id: str = "author-1",
    status: NovelStatus = NovelStatus.DRAFT,
) -> Novel:
    return Novel(
        id=NovelId(novel_id),
        title=novel_id,
        author_id=UserId(author_id),
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


def test_novel_repository_matches_port_behavior_and_ordering() -> None:
    repository = InMemoryNovelRepository(
        [
            _novel("novel-b", "2026-01-02", status=NovelStatus.PUBLISHED),
            _novel("novel-a", "2026-01-02", status=NovelStatus.PUBLISHED),
            _novel("novel-c", "2026-01-03", author_id="author-2"),
        ]
    )

    assert [novel.id for novel in repository.list_all(10, 0)] == [
        NovelId("novel-c"),
        NovelId("novel-a"),
        NovelId("novel-b"),
    ]
    assert [novel.id for novel in repository.list_published()] == [
        NovelId("novel-a"),
        NovelId("novel-b"),
    ]
    assert [novel.id for novel in repository.list_by_author(UserId("author-1"))] == [
        NovelId("novel-a"),
        NovelId("novel-b"),
    ]
    assert repository.count_all() == 3

    replacement = _novel("novel-b", "2026-01-04", status=NovelStatus.PUBLISHED)
    assert repository.save(replacement) is replacement
    assert repository.get(NovelId("novel-b")) is replacement


def test_library_repository_is_idempotent_and_orders_entries() -> None:
    repository = InMemoryLibraryRepository()
    first = LibraryEntry(UserId("reader-1"), NovelId("novel-b"), "2026-01-02")
    second = LibraryEntry(UserId("reader-1"), NovelId("novel-a"), "2026-01-02")
    replacement = LibraryEntry(UserId("reader-1"), NovelId("novel-b"), "2026-01-03")

    assert repository.save(first) == first
    assert repository.save(second) == second
    assert repository.save(replacement) == first
    assert repository.list_by_user(UserId("reader-1")) == [second, first]

    repository.delete(UserId("reader-1"), NovelId("novel-a"))
    assert repository.list_by_user(UserId("reader-1")) == [first]


def test_repository_instances_do_not_share_state() -> None:
    first = InMemoryNovelRepository([_novel("novel-1", "2026-01-01")])
    second = InMemoryNovelRepository()

    assert first.get(NovelId("novel-1")) is not None
    assert second.get(NovelId("novel-1")) is None
