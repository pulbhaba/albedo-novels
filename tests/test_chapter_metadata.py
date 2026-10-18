from __future__ import annotations

import pytest

from albedo_novels_core.application import (
    ChapterMetadataUseCases,
    ForbiddenError,
    NotFoundError,
)
from albedo_novels_core.domain.models import Chapter, ChapterId, Novel, NovelId, NovelStatus, UserContext, UserId
from albedo_novels_infrastructure.persistence.in_memory import InMemoryChapterRepository, InMemoryNovelRepository


class FixedIds:
    def __init__(self) -> None:
        self._next = 1

    def new_id(self) -> str:
        chapter_id = f"chapter-{self._next}"
        self._next += 1
        return chapter_id


def _novel(status: NovelStatus = NovelStatus.DRAFT) -> Novel:
    return Novel(
        id=NovelId("novel-1"),
        title="Test novel",
        author_id=UserId("author-1"),
        status=status,
        created_at="2026-08-20T00:00:00+00:00",
        updated_at="2026-08-20T00:00:00+00:00",
    )


def _use_cases(status: NovelStatus = NovelStatus.DRAFT) -> tuple[ChapterMetadataUseCases, InMemoryChapterRepository]:
    chapters = InMemoryChapterRepository()
    return ChapterMetadataUseCases(InMemoryNovelRepository([_novel(status)]), chapters, FixedIds()), chapters


def test_owner_creates_stable_chapter_ids_with_sequential_display_order() -> None:
    use_cases, _ = _use_cases()
    owner = UserContext(UserId("author-1"))

    first = use_cases.create_chapter(owner, NovelId("novel-1"), "Opening")
    second = use_cases.create_chapter(owner, NovelId("novel-1"), "The Journey")

    assert first == Chapter(NovelId("novel-1"), ChapterId("chapter-1"), "Opening", 1)
    assert second.chapter_id == ChapterId("chapter-2")
    assert second.display_order == 2
    assert not hasattr(first, "body")
    assert use_cases.list_chapters(owner, NovelId("novel-1")) == [first, second]


def test_chapter_listing_orders_metadata_by_display_order_then_id() -> None:
    use_cases, chapters = _use_cases(NovelStatus.PUBLISHED)
    chapters.save(Chapter(NovelId("novel-1"), ChapterId("chapter-z"), "Later", 2))
    chapters.save(Chapter(NovelId("novel-1"), ChapterId("chapter-b"), "Earlier B", 1))
    chapters.save(Chapter(NovelId("novel-1"), ChapterId("chapter-a"), "Earlier A", 1))

    listed = use_cases.list_chapters(UserContext(UserId("reader-1")), NovelId("novel-1"))

    assert [chapter.chapter_id for chapter in listed] == [
        ChapterId("chapter-a"),
        ChapterId("chapter-b"),
        ChapterId("chapter-z"),
    ]


def test_metadata_creation_allows_owner_and_editor_but_forbids_other_users() -> None:
    use_cases, _ = _use_cases()

    with pytest.raises(ForbiddenError):
        use_cases.create_chapter(UserContext(UserId("reader-1")), NovelId("novel-1"), "Forbidden")

    editor = UserContext(UserId("editor-1"), frozenset({"ROLE_EDITOR"}))
    assert use_cases.create_chapter(editor, NovelId("novel-1"), "Editorial note").display_order == 1


def test_listing_enforces_novel_read_access_and_missing_novels_return_not_found() -> None:
    use_cases, _ = _use_cases()

    with pytest.raises(ForbiddenError):
        use_cases.list_chapters(UserContext(UserId("reader-1")), NovelId("novel-1"))
    with pytest.raises(NotFoundError):
        use_cases.list_chapters(UserContext(UserId("author-1")), NovelId("missing"))
    with pytest.raises(NotFoundError):
        use_cases.create_chapter(UserContext(UserId("admin-1"), frozenset({"ROLE_ADMIN"})), NovelId("missing"), "Title")
