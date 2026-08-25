"""In-memory persistence adapters for framework-free tests."""
from __future__ import annotations

from collections.abc import Iterable

from albedo_novels_core.domain.models import (
    ChapterContent,
    ChapterContentMetadata,
    ChapterId,
    LibraryEntry,
    Novel,
    NovelId,
    NovelStatus,
    UserId,
)


class InMemoryContentStorage:
    """Store chapter versions independently from novel metadata."""

    def __init__(self) -> None:
        self._content: dict[tuple[NovelId, ChapterId, int], ChapterContent] = {}

    def save(self, content: ChapterContent) -> ChapterContent:
        self._content[(content.novel_id, content.chapter_id, content.version)] = content
        return content

    def get_latest(self, novel_id: NovelId, chapter_id: ChapterId) -> ChapterContent | None:
        versions = [item for item in self._content.values() if item.novel_id == novel_id and item.chapter_id == chapter_id]
        return max(versions, key=lambda item: item.version, default=None)

    def get_version(self, novel_id: NovelId, chapter_id: ChapterId, version: int) -> ChapterContent | None:
        return self._content.get((novel_id, chapter_id, version))

    def list_versions(self, novel_id: NovelId, chapter_id: ChapterId) -> list[ChapterContentMetadata]:
        versions = [item for item in self._content.values() if item.novel_id == novel_id and item.chapter_id == chapter_id]
        return [item.metadata() for item in sorted(versions, key=lambda item: item.version, reverse=True)]


class InMemoryNovelRepository:
    """Store novel metadata in an isolated, deterministic in-memory store."""

    def __init__(self, novels: Iterable[Novel] = ()) -> None:
        self._novels = {novel.id: novel for novel in novels}

    def save(self, novel: Novel) -> Novel:
        self._novels[novel.id] = novel
        return novel

    def get(self, novel_id: NovelId) -> Novel | None:
        return self._novels.get(novel_id)

    def list_published(self) -> list[Novel]:
        return self._ordered(
            novel for novel in self._novels.values() if novel.status == NovelStatus.PUBLISHED
        )

    def list_by_author(self, author_id: UserId) -> list[Novel]:
        return self._ordered(novel for novel in self._novels.values() if novel.author_id == author_id)

    def list_all(self, limit: int, offset: int) -> list[Novel]:
        return self._ordered(self._novels.values())[offset : offset + limit]

    def count_all(self) -> int:
        return len(self._novels)

    @staticmethod
    def _ordered(novels: Iterable[Novel]) -> list[Novel]:
        by_id = sorted(novels, key=lambda novel: novel.id)
        return sorted(by_id, key=lambda novel: novel.created_at, reverse=True)


class InMemoryLibraryRepository:
    """Store favorites in an isolated, in-memory repository."""

    def __init__(self, entries: Iterable[LibraryEntry] = ()) -> None:
        self._entries = {(entry.user_id, entry.novel_id): entry for entry in entries}

    def save(self, entry: LibraryEntry) -> LibraryEntry:
        key = (entry.user_id, entry.novel_id)
        if key not in self._entries:
            self._entries[key] = entry
        return self._entries[key]

    def delete(self, user_id: UserId, novel_id: NovelId) -> None:
        self._entries.pop((user_id, novel_id), None)

    def list_by_user(self, user_id: UserId) -> list[LibraryEntry]:
        entries = [entry for entry in self._entries.values() if entry.user_id == user_id]
        by_novel_id = sorted(entries, key=lambda entry: entry.novel_id)
        return sorted(by_novel_id, key=lambda entry: entry.created_at, reverse=True)
