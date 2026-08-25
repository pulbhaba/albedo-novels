"""Focused tests for the framework-free novel use cases."""
from __future__ import annotations

import pytest

from albedo_novels_core.application import (
    ConflictError,
    CreateNovelCommand,
    ForbiddenError,
    NotFoundError,
    NovelUseCases,
    UpdateNovelCommand,
)
from albedo_novels_core.domain.models import (
    LibraryEntry,
    Novel,
    NovelId,
    NovelStatus,
    UserContext,
    UserId,
)


class InMemoryNovelRepository:
    def __init__(self, novels: list[Novel] | None = None) -> None:
        self.novels = {novel.id: novel for novel in novels or []}

    def save(self, novel: Novel) -> Novel:
        self.novels[novel.id] = novel
        return novel

    def get(self, novel_id: NovelId) -> Novel | None:
        return self.novels.get(novel_id)

    def list_published(self) -> list[Novel]:
        return [novel for novel in self.novels.values() if novel.status == NovelStatus.PUBLISHED]

    def list_by_author(self, author_id: UserId) -> list[Novel]:
        return [novel for novel in self.novels.values() if novel.author_id == author_id]

    def list_all(self, limit: int, offset: int) -> list[Novel]:
        return list(self.novels.values())[offset : offset + limit]

    def count_all(self) -> int:
        return len(self.novels)


class InMemoryLibraryRepository:
    def __init__(self) -> None:
        self.entries: dict[tuple[UserId, NovelId], LibraryEntry] = {}

    def save(self, entry: LibraryEntry) -> LibraryEntry:
        self.entries[(entry.user_id, entry.novel_id)] = entry
        return entry

    def delete(self, user_id: UserId, novel_id: NovelId) -> None:
        self.entries.pop((user_id, novel_id), None)

    def list_by_user(self, user_id: UserId) -> list[LibraryEntry]:
        return [entry for entry in self.entries.values() if entry.user_id == user_id]


class FixedIds:
    def new_id(self) -> str:
        return "novel-created"


class FixedClock:
    def utcnow_iso(self) -> str:
        return "2026-08-21T00:00:00+00:00"


def _use_cases(
    novels: InMemoryNovelRepository | None = None,
    library: InMemoryLibraryRepository | None = None,
) -> tuple[NovelUseCases, InMemoryNovelRepository, InMemoryLibraryRepository]:
    novels = novels or InMemoryNovelRepository()
    library = library or InMemoryLibraryRepository()
    return NovelUseCases(novels, library, FixedIds(), FixedClock()), novels, library


def _draft() -> Novel:
    return Novel(
        id=NovelId("novel-draft"),
        title="A Draft Novel",
        author_id=UserId("author-1"),
        status=NovelStatus.DRAFT,
        created_at="2026-08-20T00:00:00+00:00",
        updated_at="2026-08-20T00:00:00+00:00",
    )


def _published() -> Novel:
    return Novel(
        id=NovelId("novel-published"),
        title="A Published Novel",
        author_id=UserId("author-1"),
        status=NovelStatus.PUBLISHED,
        created_at="2026-08-19T00:00:00+00:00",
        updated_at="2026-08-19T00:00:00+00:00",
    )


def test_create_novel_saves_a_draft_with_creator_metadata() -> None:
    use_cases, novels, _ = _use_cases()
    author = UserContext(user_id=UserId("author-1"))

    created = use_cases.create_novel(
        author,
        CreateNovelCommand("A New Novel", author.user_id, isbn="978-000000099"),
    )

    assert created == novels.get(NovelId("novel-created"))
    assert created.status is NovelStatus.DRAFT
    assert created.author_id == author.user_id
    assert created.last_modified_user_id == author.user_id
    assert created.created_at == "2026-08-21T00:00:00+00:00"


def test_publish_novel_updates_the_existing_record() -> None:
    repository = InMemoryNovelRepository([_draft()])
    use_cases, novels, _ = _use_cases(repository)
    editor = UserContext(UserId("editor-1"), frozenset({"ROLE_EDITOR"}))

    published = use_cases.publish_novel(editor, NovelId("novel-draft"))

    assert published.status is NovelStatus.PUBLISHED
    assert published.updated_at == "2026-08-21T00:00:00+00:00"
    assert published.last_modified_user_id == editor.user_id
    assert novels.get(NovelId("novel-draft")) == published


def test_publish_novel_requires_editor_or_admin_role() -> None:
    use_cases, _, _ = _use_cases(InMemoryNovelRepository([_draft()]))

    with pytest.raises(ForbiddenError, match="ROLE_EDITOR"):
        use_cases.publish_novel(UserContext(UserId("reader-1")), NovelId("novel-draft"))


def test_publish_novel_rejects_republishing_an_existing_publication() -> None:
    use_cases, _, _ = _use_cases(InMemoryNovelRepository([_published()]))
    editor = UserContext(UserId("editor-1"), frozenset({"ROLE_EDITOR"}))

    with pytest.raises(ConflictError, match="already published"):
        use_cases.publish_novel(editor, NovelId("novel-published"))


def test_update_draft_changes_owned_metadata_and_audit_fields() -> None:
    repository = InMemoryNovelRepository([_draft()])
    use_cases, novels, _ = _use_cases(repository)
    owner = UserContext(UserId("author-1"))

    updated = use_cases.update_draft(
        owner,
        NovelId("novel-draft"),
        UpdateNovelCommand(title="A Better Draft", isbn="978-000000111", update_isbn=True),
    )

    assert updated.title == "A Better Draft"
    assert updated.isbn == "978-000000111"
    assert updated.status is NovelStatus.DRAFT
    assert updated.updated_at == "2026-08-21T00:00:00+00:00"
    assert updated.last_modified_user_id == owner.user_id
    assert novels.get(updated.id) == updated


def test_update_draft_requires_owner_and_draft_status() -> None:
    use_cases, _, _ = _use_cases(InMemoryNovelRepository([_draft(), _published()]))

    with pytest.raises(ForbiddenError):
        use_cases.update_draft(UserContext(UserId("reader-1")), NovelId("novel-draft"), UpdateNovelCommand(title="Nope"))
    with pytest.raises(ConflictError):
        use_cases.update_draft(UserContext(UserId("author-1")), NovelId("novel-published"), UpdateNovelCommand(title="Nope"))


def test_get_novel_allows_published_novels_and_owned_drafts() -> None:
    repository = InMemoryNovelRepository([_draft(), _published()])
    use_cases, _, _ = _use_cases(repository)

    assert use_cases.get_novel(UserContext(UserId("reader-1")), NovelId("novel-published")) == _published()
    assert use_cases.get_novel(UserContext(UserId("author-1")), NovelId("novel-draft")) == _draft()


def test_get_novel_rejects_unreadable_drafts_and_missing_novels() -> None:
    use_cases, _, _ = _use_cases(InMemoryNovelRepository([_draft()]))
    reader = UserContext(UserId("reader-1"))

    with pytest.raises(ForbiddenError):
        use_cases.get_novel(reader, NovelId("novel-draft"))
    with pytest.raises(NotFoundError):
        use_cases.get_novel(reader, NovelId("novel-missing"))


def test_add_favorite_persists_entry_for_a_readable_novel() -> None:
    repository = InMemoryNovelRepository([_published()])
    use_cases, _, library = _use_cases(repository)
    reader = UserContext(UserId("reader-1"))

    entry = use_cases.add_favorite(reader, NovelId("novel-published"))

    assert entry == LibraryEntry(reader.user_id, NovelId("novel-published"), "2026-08-21T00:00:00+00:00")
    assert library.list_by_user(reader.user_id) == [entry]

    assert use_cases.add_favorite(reader, NovelId("novel-published")) == entry
    assert library.list_by_user(reader.user_id) == [entry]


def test_add_favorite_rejects_a_draft_the_reader_cannot_read() -> None:
    use_cases, _, library = _use_cases(InMemoryNovelRepository([_draft()]))

    with pytest.raises(ForbiddenError):
        use_cases.add_favorite(UserContext(UserId("reader-1")), NovelId("novel-draft"))

    assert library.list_by_user(UserId("reader-1")) == []


def test_remove_favorite_is_idempotent_and_private_to_the_current_user() -> None:
    use_cases, _, library = _use_cases()
    reader = UserContext(UserId("reader-1"))
    other_reader = UserContext(UserId("reader-2"))
    library.save(LibraryEntry(reader.user_id, NovelId("novel-published"), "2026-08-21T00:00:00+00:00"))
    library.save(LibraryEntry(other_reader.user_id, NovelId("novel-published"), "2026-08-21T00:00:00+00:00"))

    use_cases.remove_favorite(reader, NovelId("novel-published"))
    use_cases.remove_favorite(reader, NovelId("novel-published"))

    assert library.list_by_user(reader.user_id) == []
    assert len(library.list_by_user(other_reader.user_id)) == 1


def test_list_library_is_private_and_omits_missing_or_unreadable_novels() -> None:
    private_draft = _draft()
    repository = InMemoryNovelRepository([_published(), private_draft])
    library = InMemoryLibraryRepository()
    reader = UserContext(UserId("reader-1"))
    use_cases, _, _ = _use_cases(repository, library)
    library.save(LibraryEntry(reader.user_id, NovelId("novel-published"), "2026-08-20T00:00:00+00:00"))
    library.save(LibraryEntry(reader.user_id, private_draft.id, "2026-08-21T00:00:00+00:00"))
    library.save(LibraryEntry(reader.user_id, NovelId("novel-missing"), "2026-08-22T00:00:00+00:00"))
    library.save(LibraryEntry(UserId("other-reader"), NovelId("novel-published"), "2026-08-23T00:00:00+00:00"))

    items = use_cases.list_library(reader)

    assert [(item.novel.id, item.favorited_at) for item in items] == [
        (NovelId("novel-published"), "2026-08-20T00:00:00+00:00")
    ]
