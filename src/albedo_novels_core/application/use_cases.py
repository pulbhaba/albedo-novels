from __future__ import annotations

from dataclasses import dataclass

from albedo_novels_core.application.ports import Clock, IdGenerator, LibraryRepository, NovelRepository
from albedo_novels_core.domain.models import (
    LibraryEntry,
    Novel,
    NovelId,
    NovelStatus,
    UserContext,
)


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class ForbiddenError(Exception):
    """Raised when the current user cannot perform an action."""


@dataclass(frozen=True)
class CreateNovelCommand:
    title: str
    body: str = ""
    summary: str = ""


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
            owner_id=user.user_id,
            title=command.title,
            summary=command.summary,
            body=command.body,
            status=NovelStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )
        return self._novels.save(novel)

    def publish_novel(self, user: UserContext, novel_id: NovelId) -> Novel:
        if not user.can_publish:
            raise ForbiddenError("Publishing requires ROLE_EDITOR or ROLE_ADMIN.")

        novel = self._load_novel(novel_id)
        published = novel.publish(updated_at=self._clock.utcnow_iso())
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

    def _load_novel(self, novel_id: NovelId) -> Novel:
        novel = self._novels.get(novel_id)
        if novel is None:
            raise NotFoundError("Novel was not found.")
        return novel
