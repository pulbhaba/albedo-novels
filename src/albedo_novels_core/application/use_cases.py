from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from albedo_novels_core.application.ports import (
    Clock,
    IdGenerator,
    LibraryRepository,
    NovelRepository,
)
from albedo_novels_core.domain.models import (
    LibraryEntry,
    LibraryNovel,
    Novel,
    NovelId,
    NovelStatus,
    UserContext,
    UserId,
)


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class ForbiddenError(Exception):
    """Raised when the current user cannot perform an action."""


@dataclass(frozen=True)
class CreateNovelCommand:
    title: str
    author_id: UserId
    isbn: str | None = None


@dataclass(frozen=True)
class ListNovelsQuery:
    """Pagination parameters for the listing use case."""

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class NovelListPage:
    """A single page of novels plus the total count."""

    items: Sequence[Novel]
    total: int
    limit: int
    offset: int


# Default page size when the caller does not provide one. Kept conservative
# because /novels is the public listing endpoint and the request is
# intentionally simple for this first cut.
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100


class NovelUseCases:
    def __init__(
        self,
        novels: NovelRepository,
        library: LibraryRepository,
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        self._novels = novels
        self._library = library
        self._ids = ids
        self._clock = clock

    def create_novel(self, user: UserContext, command: CreateNovelCommand) -> Novel:
        now = self._clock.utcnow_iso()
        novel = Novel(
            id=NovelId(self._ids.new_id()),
            title=command.title,
            author_id=command.author_id,
            status=NovelStatus.DRAFT,
            created_at=now,
            updated_at=now,
            isbn=command.isbn,
            last_modified_user_id=user.user_id,
        )
        return self._novels.save(novel)

    def publish_novel(self, user: UserContext, novel_id: NovelId) -> Novel:
        if not user.can_publish:
            raise ForbiddenError("Publishing requires ROLE_EDITOR or ROLE_ADMIN.")

        novel = self._load_novel(novel_id)
        published = novel.publish(
            updated_at=self._clock.utcnow_iso(),
            last_modified_user_id=user.user_id,
        )
        return self._novels.save(published)

    def add_favorite(self, user: UserContext, novel_id: NovelId) -> LibraryEntry:
        novel = self._load_novel(novel_id)
        if not novel.is_readable_by(user):
            raise ForbiddenError("Novel is not readable by the current user.")

        entry = LibraryEntry(
            user_id=user.user_id,
            novel_id=novel.id,
            created_at=self._clock.utcnow_iso(),
        )
        return self._library.save(entry)

    def remove_favorite(self, user: UserContext, novel_id: NovelId) -> None:
        """Remove this user's favorite, treating an absent entry as success."""
        self._library.delete(user.user_id, novel_id)

    def list_library(self, user: UserContext) -> list[LibraryNovel]:
        """Return this user's readable favorites in repository order.

        Library rows can outlive a novel or become unreadable after a status
        change, so those rows are intentionally omitted from the view.
        """
        items: list[LibraryNovel] = []
        for entry in self._library.list_by_user(user.user_id):
            novel = self._novels.get(entry.novel_id)
            if novel is not None and novel.is_readable_by(user):
                items.append(LibraryNovel(novel=novel, favorited_at=entry.created_at))
        return items

    def list_novels(self, query: ListNovelsQuery) -> NovelListPage:
        limit, offset = _normalize_pagination(query.limit, query.offset)
        items = self._novels.list_all(limit=limit, offset=offset)
        total = self._novels.count_all()
        return NovelListPage(items=items, total=total, limit=limit, offset=offset)

    def get_novel(self, user: UserContext, novel_id: NovelId) -> Novel:
        novel = self._load_novel(novel_id)
        if not novel.is_readable_by(user):
            raise ForbiddenError("Novel is not readable by the current user.")
        return novel

    def _load_novel(self, novel_id: NovelId) -> Novel:
        novel = self._novels.get(novel_id)
        if novel is None:
            raise NotFoundError("Novel was not found.")
        return novel


def _normalize_pagination(limit: int, offset: int) -> tuple[int, int]:
    if limit <= 0:
        limit = DEFAULT_LIST_LIMIT
    if limit > MAX_LIST_LIMIT:
        limit = MAX_LIST_LIMIT
    if offset < 0:
        offset = 0
    return limit, offset
