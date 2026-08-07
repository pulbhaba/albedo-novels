"""In-memory seeded novel DAO used for local development and tests.

This module is intentionally a stand-in for the production MySQL DAO. It
implements the same `NovelRepository` port so the FastAPI/Lambda adapters and
the use cases can be wired against it today and swapped for the real
persistence adapter later without changing the call sites.

The DAO is mutable and process-local. It is **not** safe to share across
workers. The class is exported under the `dao_test` namespace inside this
package so tests can replace it cleanly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from albedo_novels_core.domain.models import (
    Author,
    Novel,
    NovelId,
    NovelStatus,
    UserId,
)


@dataclass(frozen=True)
class SeededNovel:
    """Static description of a novel to be materialised by `SeededNovelDao`."""

    id: str
    title: str
    author_id: str
    author_display_name: str
    cover_image_url: str
    status: NovelStatus
    created_at: str
    updated_at: str
    owner_id: str


DEFAULT_SEED: tuple[SeededNovel, ...] = (
    SeededNovel(
        id="novel-001",
        title="The Glass Compass",
        author_id="user-1",
        author_display_name="Asha Lindgren",
        cover_image_url="https://cdn.albedo.example/covers/glass-compass.jpg",
        status=NovelStatus.PUBLISHED,
        created_at="2026-01-04T09:30:00+00:00",
        updated_at="2026-01-12T12:15:00+00:00",
        owner_id="user-1",
    ),
    SeededNovel(
        id="novel-002",
        title="A Map for Forgetting",
        author_id="user-2",
        author_display_name="Rohan Patel",
        cover_image_url="https://cdn.albedo.example/covers/map-for-forgetting.jpg",
        status=NovelStatus.PUBLISHED,
        created_at="2026-02-18T18:05:00+00:00",
        updated_at="2026-02-22T08:42:00+00:00",
        owner_id="user-2",
    ),
    SeededNovel(
        id="novel-003",
        title="Saltwater Letters",
        author_id="user-3",
        author_display_name="Marisol Tan",
        cover_image_url="https://cdn.albedo.example/covers/saltwater-letters.jpg",
        status=NovelStatus.PUBLISHED,
        created_at="2026-03-01T07:00:00+00:00",
        updated_at="2026-03-01T07:00:00+00:00",
        owner_id="user-3",
    ),
    SeededNovel(
        id="novel-004",
        title="Draft: Iron Orchids",
        author_id="user-1",
        author_display_name="Asha Lindgren",
        cover_image_url="https://cdn.albedo.example/covers/iron-orchids.jpg",
        status=NovelStatus.DRAFT,
        created_at="2026-04-09T15:20:00+00:00",
        updated_at="2026-08-01T10:00:00+00:00",
        owner_id="user-1",
    ),
)


def _materialise(seed: SeededNovel) -> Novel:
    return Novel(
        id=NovelId(seed.id),
        title=seed.title,
        author=Author(id=UserId(seed.author_id), display_name=seed.author_display_name),
        cover_image_url=seed.cover_image_url,
        status=seed.status,
        created_at=seed.created_at,
        updated_at=seed.updated_at,
        owner_id=UserId(seed.owner_id),
    )


class SeededNovelDao:
    """In-memory novel repository seeded with a static dataset.

    Exposed as `dao_test.SeededNovelDao` so production code can wire the real
    MySQL DAO while tests, local development, and the listing endpoint can
    fall back to this fixture-style implementation.
    """

    def __init__(self, seeds: Iterable[SeededNovel] | None = None) -> None:
        materialised = [_materialise(seed) for seed in (seeds if seeds is not None else DEFAULT_SEED)]
        # Newest first, then stable by ascending id, so list_all(limit,
        # offset) is deterministic across calls.
        self._novels = _ordered(materialised)

    def save(self, novel: Novel) -> Novel:
        self._novels = [existing for existing in self._novels if existing.id != novel.id]
        self._novels.append(novel)
        self._novels = _ordered(self._novels)
        return novel

    def get(self, novel_id: NovelId) -> Novel | None:
        return next((novel for novel in self._novels if novel.id == novel_id), None)

    def list_published(self) -> list[Novel]:
        return [novel for novel in self._novels if novel.status == NovelStatus.PUBLISHED]

    def list_by_owner(self, owner_id: UserId) -> list[Novel]:
        return [novel for novel in self._novels if novel.owner_id == owner_id]

    def list_all(self, limit: int, offset: int) -> list[Novel]:
        return self._novels[offset : offset + limit]

    def count_all(self) -> int:
        return len(self._novels)


def _ordered(novels: Iterable[Novel]) -> list[Novel]:
    """Order by created time descending and ID ascending."""
    by_id = sorted(novels, key=lambda novel: novel.id)
    return sorted(by_id, key=lambda novel: novel.created_at, reverse=True)


# Alias exposed for tests and short-lived wiring scripts. Production code
# should depend on the `NovelRepository` port, not on this alias directly.
dao_test = SeededNovelDao
