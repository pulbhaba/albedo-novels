from __future__ import annotations

import pytest

from albedo_novels_core.application import ChapterContentUseCases, ForbiddenError, NotFoundError
from albedo_novels_core.domain.models import ChapterId, Novel, NovelId, NovelStatus, UserContext, UserId
from albedo_novels_infrastructure.persistence.in_memory import InMemoryContentStorage, InMemoryNovelRepository


class FixedClock:
    def utcnow_iso(self) -> str:
        return "2026-08-21T00:00:00+00:00"


def _novel(status: NovelStatus = NovelStatus.DRAFT) -> Novel:
    return Novel(
        id=NovelId("novel-1"),
        title="Test novel",
        author_id=UserId("author-1"),
        status=status,
        created_at="2026-08-20T00:00:00+00:00",
        updated_at="2026-08-20T00:00:00+00:00",
    )


def _use_cases(status: NovelStatus = NovelStatus.DRAFT) -> ChapterContentUseCases:
    return ChapterContentUseCases(
        InMemoryNovelRepository([_novel(status)]),
        InMemoryContentStorage(),
        FixedClock(),
    )


def test_owner_writes_versions_and_readers_only_receive_metadata_in_listing() -> None:
    use_cases = _use_cases(NovelStatus.PUBLISHED)
    owner = UserContext(UserId("author-1"))

    first = use_cases.write(owner, NovelId("novel-1"), ChapterId("chapter-1"), "First draft")
    second = use_cases.write(owner, NovelId("novel-1"), ChapterId("chapter-1"), "Final draft")

    assert first.version == 1
    assert second.version == 2
    assert use_cases.get_latest(UserContext(UserId("reader-1")), NovelId("novel-1"), ChapterId("chapter-1")) == second
    assert [item.version for item in use_cases.list_versions(owner, NovelId("novel-1"), ChapterId("chapter-1"))] == [2, 1]


def test_draft_content_is_private_and_writes_require_owner_or_editor() -> None:
    use_cases = _use_cases()
    reader = UserContext(UserId("reader-1"))

    with pytest.raises(ForbiddenError):
        use_cases.get_latest(reader, NovelId("novel-1"), ChapterId("chapter-1"))
    with pytest.raises(ForbiddenError):
        use_cases.write(reader, NovelId("novel-1"), ChapterId("chapter-1"), "Nope")

    with pytest.raises(NotFoundError):
        use_cases.get_latest(UserContext(UserId("author-1")), NovelId("novel-1"), ChapterId("chapter-1"))
