from __future__ import annotations

from pathlib import Path

import pytest

from albedo_novels_core.domain.models import ChapterContent, ChapterId, NovelId, UserId
from albedo_novels_infrastructure.persistence.file_content_storage import FileContentStorage


def _content(version: int, body: str | None = None) -> ChapterContent:
    return ChapterContent(
        novel_id=NovelId("novel-1"),
        chapter_id=ChapterId("chapter-1"),
        version=version,
        body=body if body is not None else f"Chapter version {version}",
        created_at=f"2026-10-25T00:00:0{version}+00:00",
        created_by=UserId("author-1"),
    )


def test_save_and_read_versions_after_recreating_adapter(tmp_path: Path) -> None:
    first_adapter = FileContentStorage(tmp_path)
    first = _content(1, "Opening — café")
    second = _content(2, "The next chapter")
    first_adapter.save(first)
    first_adapter.save(second)

    restarted_adapter = FileContentStorage(tmp_path)

    assert restarted_adapter.get_latest(NovelId("novel-1"), ChapterId("chapter-1")) == second
    assert restarted_adapter.get_version(NovelId("novel-1"), ChapterId("chapter-1"), 1) == first
    assert restarted_adapter.list_versions(NovelId("novel-1"), ChapterId("chapter-1")) == [
        second.metadata(),
        first.metadata(),
    ]


def test_missing_chapter_content_returns_none_or_empty_list(tmp_path: Path) -> None:
    storage = FileContentStorage(tmp_path)

    assert storage.get_latest(NovelId("novel-1"), ChapterId("missing")) is None
    assert storage.get_version(NovelId("novel-1"), ChapterId("missing"), 1) is None
    assert storage.list_versions(NovelId("novel-1"), ChapterId("missing")) == []
    assert storage.get_version(NovelId("novel-1"), ChapterId("chapter-1"), 0) is None


def test_existing_version_is_not_overwritten(tmp_path: Path) -> None:
    storage = FileContentStorage(tmp_path)
    original = _content(1, "Original")
    storage.save(original)

    with pytest.raises(FileExistsError):
        storage.save(_content(1, "Replacement"))

    assert storage.get_version(original.novel_id, original.chapter_id, 1) == original


def test_identifiers_are_encoded_as_safe_path_components(tmp_path: Path) -> None:
    storage = FileContentStorage(tmp_path)
    content = ChapterContent(
        novel_id=NovelId("../novel/escape"),
        chapter_id=ChapterId("../../chapter/escape"),
        version=1,
        body="Safe path",
        created_at="2026-10-25T00:00:00+00:00",
        created_by=UserId("author-1"),
    )

    storage.save(content)

    version_path = next(tmp_path.rglob("1.json"))
    assert version_path.is_relative_to(tmp_path.resolve())
    assert storage.get_latest(content.novel_id, content.chapter_id) == content


def test_content_directory_must_not_be_empty() -> None:
    with pytest.raises(ValueError, match="directory is required"):
        FileContentStorage(" ")
