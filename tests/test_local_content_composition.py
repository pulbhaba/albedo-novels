from __future__ import annotations

from pathlib import Path

import pytest

from albedo_novels_core.domain.models import ChapterId, NovelId, UserContext, UserId
from albedo_novels_infrastructure.composition import build_content_use_cases
from albedo_novels_infrastructure.persistence.file_content_storage import FileContentStorage
from albedo_novels_infrastructure.persistence.in_memory import InMemoryContentStorage


def test_local_composition_uses_filesystem_storage_when_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NOVELS_CHAPTER_CONTENT_DIR", str(tmp_path))
    owner = UserContext(UserId("user-1"))
    novel_id = NovelId("novel-004")
    chapter_id = ChapterId("chapter-local-file-storage")

    written = build_content_use_cases().write(owner, novel_id, chapter_id, "Persistent local content")
    restarted = build_content_use_cases()

    assert isinstance(restarted._content, FileContentStorage)
    assert restarted.get_latest(owner, novel_id, chapter_id) == written


def test_local_composition_keeps_in_memory_storage_when_directory_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NOVELS_CHAPTER_CONTENT_DIR", raising=False)

    assert isinstance(build_content_use_cases()._content, InMemoryContentStorage)
