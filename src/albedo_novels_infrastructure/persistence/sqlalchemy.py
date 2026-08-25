"""SQLAlchemy persistence adapters for novel metadata and favorites."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from albedo_novels_core.domain.models import LibraryEntry, Novel, NovelId, NovelStatus, UserId
from albedo_novels_infrastructure.config import novels_table_name


_NOVELS_TABLE_NAME = novels_table_name()


class Base(DeclarativeBase):
    pass


class NovelRow(Base):
    __tablename__ = _NOVELS_TABLE_NAME
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="novels_status_check"),
        Index("novels_status_created_idx", "status", "created_at"),
        Index("novels_author_created_idx", "author_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    last_modified_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LibraryEntryRow(Base):
    __tablename__ = "library_entries"
    __table_args__ = (Index("library_entries_user_created_idx", "user_id", "created_at"),)
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    novel_id: Mapped[str] = mapped_column(ForeignKey(f"{_NOVELS_TABLE_NAME}.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


SessionFactory = Callable[[], Session]


class SqlAlchemyNovelRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def save(self, novel: Novel) -> Novel:
        with self._session_factory() as session:
            row = session.get(NovelRow, str(novel.id))
            if row is None:
                row = NovelRow(id=str(novel.id))
                session.add(row)
            _copy_novel_to_row(novel, row)
            session.commit()
        return novel

    def get(self, novel_id: NovelId) -> Novel | None:
        with self._session_factory() as session:
            row = session.get(NovelRow, str(novel_id))
            return _novel_from_row(row) if row else None

    def list_published(self) -> list[Novel]:
        return self._list(NovelRow.status == NovelStatus.PUBLISHED.value)

    def list_by_author(self, author_id: UserId) -> list[Novel]:
        return self._list(NovelRow.author_id == str(author_id))

    def list_all(self, limit: int, offset: int) -> list[Novel]:
        with self._session_factory() as session:
            rows = session.scalars(select(NovelRow).order_by(NovelRow.created_at.desc(), NovelRow.id.asc()).limit(limit).offset(offset)).all()
            return [_novel_from_row(row) for row in rows]

    def count_all(self) -> int:
        with self._session_factory() as session:
            return int(session.scalar(select(func.count()).select_from(NovelRow)) or 0)

    def _list(self, *criteria: Any) -> list[Novel]:
        with self._session_factory() as session:
            rows = session.scalars(select(NovelRow).where(*criteria).order_by(NovelRow.created_at.desc(), NovelRow.id.asc())).all()
            return [_novel_from_row(row) for row in rows]


class SqlAlchemyLibraryRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def save(self, entry: LibraryEntry) -> LibraryEntry:
        with self._session_factory() as session:
            row = session.get(LibraryEntryRow, (str(entry.user_id), str(entry.novel_id)))
            if row is None:
                session.add(LibraryEntryRow(user_id=str(entry.user_id), novel_id=str(entry.novel_id), created_at=entry.created_at))
            session.commit()
        return entry

    def delete(self, user_id: UserId, novel_id: NovelId) -> None:
        with self._session_factory() as session:
            session.execute(delete(LibraryEntryRow).where(LibraryEntryRow.user_id == str(user_id), LibraryEntryRow.novel_id == str(novel_id)))
            session.commit()

    def list_by_user(self, user_id: UserId) -> list[LibraryEntry]:
        with self._session_factory() as session:
            rows = session.scalars(select(LibraryEntryRow).where(LibraryEntryRow.user_id == str(user_id)).order_by(LibraryEntryRow.created_at.desc(), LibraryEntryRow.novel_id.asc())).all()
            return [LibraryEntry(UserId(row.user_id), NovelId(row.novel_id), row.created_at) for row in rows]


def _copy_novel_to_row(novel: Novel, row: NovelRow) -> None:
    row.title = novel.title
    row.author_id = str(novel.author_id)
    row.status = novel.status.value
    row.created_at = novel.created_at
    row.updated_at = novel.updated_at
    row.isbn = novel.isbn
    row.last_modified_user_id = str(novel.last_modified_user_id) if novel.last_modified_user_id else None


def _novel_from_row(row: NovelRow) -> Novel:
    return Novel(
        id=NovelId(row.id), title=row.title, author_id=UserId(row.author_id), status=NovelStatus(row.status),
        created_at=row.created_at, updated_at=row.updated_at, isbn=row.isbn,
        last_modified_user_id=UserId(row.last_modified_user_id) if row.last_modified_user_id else None,
    )
