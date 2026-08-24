from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from albedo_novels_core.domain.models import LibraryEntry, Novel, NovelId, NovelStatus, UserId
from albedo_novels_infrastructure.persistence.sqlalchemy import (
    Base,
    LibraryEntryRow,
    NovelRow,
    SqlAlchemyLibraryRepository,
    SqlAlchemyNovelRepository,
)


def _repositories() -> tuple[SqlAlchemyNovelRepository, SqlAlchemyLibraryRepository]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return SqlAlchemyNovelRepository(sessions), SqlAlchemyLibraryRepository(sessions)


def test_schema_creates_only_the_service_owned_tables() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    assert set(inspect(engine).get_table_names()) == {"novels", "library_entries"}
    assert {column["name"] for column in inspect(engine).get_columns("novels")} == {
        "id", "title", "author_id", "status", "created_at", "updated_at", "isbn", "last_modified_user_id",
    }
    assert {column["name"] for column in inspect(engine).get_columns("library_entries")} == {
        "user_id", "novel_id", "created_at",
    }
    assert NovelRow.__table__.c.status.nullable is False
    assert LibraryEntryRow.__table__.c.novel_id.foreign_keys


def test_sqlalchemy_novel_repository_round_trips_metadata_only() -> None:
    novels, _ = _repositories()
    novel = Novel(
        id=NovelId("novel-1"),
        title="The Title",
        author_id=UserId("author-1"),
        status=NovelStatus.DRAFT,
        created_at="2026-08-01T00:00:00+00:00",
        updated_at="2026-08-01T00:00:00+00:00",
        isbn="978-000000001",
    )

    assert novels.save(novel) == novel
    assert novels.get(NovelId("novel-1")) == novel
    assert novels.list_by_author(UserId("author-1")) == [novel]
    assert novels.count_all() == 1

    updated = Novel(
        id=novel.id, title="Updated title", author_id=novel.author_id,
        status=novel.status, created_at=novel.created_at,
        updated_at="2026-08-02T00:00:00+00:00", isbn=novel.isbn,
    )
    assert novels.save(updated) == updated
    assert novels.get(novel.id) == updated


def test_sqlalchemy_library_repository_is_idempotent() -> None:
    novels, library = _repositories()
    novels.save(
        Novel(
            id=NovelId("novel-1"), title="Title", author_id=UserId("author-1"),
            status=NovelStatus.PUBLISHED, created_at="2026-08-01", updated_at="2026-08-01",
        )
    )
    entry = LibraryEntry(UserId("reader-1"), NovelId("novel-1"), "2026-08-02")

    assert library.save(entry) == entry
    assert library.save(entry) == entry
    assert library.list_by_user(UserId("reader-1")) == [entry]

    library.delete(UserId("reader-1"), NovelId("novel-1"))
    assert library.list_by_user(UserId("reader-1")) == []
