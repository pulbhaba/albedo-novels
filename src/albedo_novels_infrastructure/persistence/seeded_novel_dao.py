"""In-memory seeded novel DAO used for local development and tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from albedo_novels_core.domain.models import Novel, NovelId, NovelStatus, UserId


@dataclass(frozen=True)
class SeededNovel:
    id: str
    title: str
    author_id: str
    status: NovelStatus
    created_at: str
    updated_at: str
    isbn: str | None = None


DEFAULT_SEED: tuple[SeededNovel, ...] = (
    SeededNovel("novel-001", "The Glass Compass", "user-1", NovelStatus.PUBLISHED, "2026-01-04T09:30:00+00:00", "2026-01-12T12:15:00+00:00", "978-000000001"),
    SeededNovel("novel-002", "A Map for Forgetting", "user-2", NovelStatus.PUBLISHED, "2026-02-18T18:05:00+00:00", "2026-02-22T08:42:00+00:00", "978-000000002"),
    SeededNovel("novel-003", "Saltwater Letters", "user-3", NovelStatus.PUBLISHED, "2026-03-01T07:00:00+00:00", "2026-03-01T07:00:00+00:00", "978-000000003"),
    SeededNovel("novel-004", "Draft: Iron Orchids", "user-1", NovelStatus.DRAFT, "2026-04-09T15:20:00+00:00", "2026-08-01T10:00:00+00:00"),
)


def _materialise(seed: SeededNovel) -> Novel:
    return Novel(
        id=NovelId(seed.id),
        title=seed.title,
        author_id=UserId(seed.author_id),
        status=seed.status,
        created_at=seed.created_at,
        updated_at=seed.updated_at,
        isbn=seed.isbn,
        last_modified_user_id=UserId(seed.author_id),
    )


class SeededNovelDao:
    def __init__(self, seeds: Iterable[SeededNovel] | None = None) -> None:
        self._novels = _ordered([_materialise(seed) for seed in (seeds if seeds is not None else DEFAULT_SEED)])

    def save(self, novel: Novel) -> Novel:
        self._novels = _ordered([existing for existing in self._novels if existing.id != novel.id] + [novel])
        return novel

    def get(self, novel_id: NovelId) -> Novel | None:
        return next((novel for novel in self._novels if novel.id == novel_id), None)

    def list_published(self) -> list[Novel]:
        return [novel for novel in self._novels if novel.status == NovelStatus.PUBLISHED]

    def list_by_author(self, author_id: UserId) -> list[Novel]:
        return [novel for novel in self._novels if novel.author_id == author_id]

    def list_all(self, limit: int, offset: int) -> list[Novel]:
        return self._novels[offset : offset + limit]

    def count_all(self) -> int:
        return len(self._novels)


def _ordered(novels: Iterable[Novel]) -> list[Novel]:
    by_id = sorted(novels, key=lambda novel: novel.id)
    return sorted(by_id, key=lambda novel: novel.created_at, reverse=True)


dao_test = SeededNovelDao
