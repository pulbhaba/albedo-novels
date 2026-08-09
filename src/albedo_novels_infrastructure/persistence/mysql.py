"""MySQL adapters for novel metadata and library favorites.

The adapters accept a connection factory instead of opening connections in the
core layer. This keeps the database driver and transaction lifecycle entirely
inside infrastructure and makes the adapters straightforward to test with a
small DB-API-shaped fake.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from albedo_novels_core.domain.models import (
    Author,
    LibraryEntry,
    Novel,
    NovelId,
    NovelStatus,
    UserId,
)


ConnectionFactory = Callable[[], Any]


class MySqlNovelRepository:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def save(self, novel: Novel) -> Novel:
        _execute(
            self._connection_factory,
            """
            INSERT INTO novels (
                id, title, author_id, author_display_name, cover_image_url,
                status, created_at, updated_at, owner_id, isbn,
                external_code, last_modified_user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), author_id = VALUES(author_id),
                author_display_name = VALUES(author_display_name),
                cover_image_url = VALUES(cover_image_url),
                status = VALUES(status), updated_at = VALUES(updated_at),
                owner_id = VALUES(owner_id), isbn = VALUES(isbn),
                external_code = VALUES(external_code),
                last_modified_user_id = VALUES(last_modified_user_id)
            """,
            (
                str(novel.id),
                novel.title,
                str(novel.author.id),
                novel.author.display_name,
                novel.cover_image_url,
                novel.status.value,
                novel.created_at,
                novel.updated_at,
                str(novel.owner_id),
                novel.isbn,
                novel.external_code,
                str(novel.last_modified_user_id) if novel.last_modified_user_id else None,
            ),
        )
        return novel

    def get(self, novel_id: NovelId) -> Novel | None:
        rows = _fetch_all(
            self._connection_factory,
            "SELECT * FROM novels WHERE id = %s",
            (str(novel_id),),
        )
        return _novel_from_row(rows[0]) if rows else None

    def list_published(self) -> list[Novel]:
        return self._list("WHERE status = %s", (NovelStatus.PUBLISHED.value,))

    def list_by_owner(self, owner_id: UserId) -> list[Novel]:
        return self._list("WHERE owner_id = %s", (str(owner_id),))

    def list_all(self, limit: int, offset: int) -> list[Novel]:
        return self._list("", (), limit=limit, offset=offset)

    def count_all(self) -> int:
        rows = _fetch_all(self._connection_factory, "SELECT COUNT(*) AS total FROM novels", ())
        return int(rows[0]["total"]) if rows else 0

    def _list(self, where: str, params: tuple[Any, ...], *, limit: int | None = None, offset: int = 0) -> list[Novel]:
        pagination = " LIMIT %s OFFSET %s" if limit is not None else ""
        query_params = params + ((limit, offset) if limit is not None else ())
        rows = _fetch_all(
            self._connection_factory,
            f"SELECT * FROM novels {where} ORDER BY created_at DESC, id ASC{pagination}",
            query_params,
        )
        return [_novel_from_row(row) for row in rows]


class MySqlLibraryRepository:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def save(self, entry: LibraryEntry) -> LibraryEntry:
        _execute(
            self._connection_factory,
            """
            INSERT INTO library_entries (user_id, novel_id, created_at)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE created_at = created_at
            """,
            (str(entry.user_id), str(entry.novel_id), entry.created_at),
        )
        return entry

    def delete(self, user_id: UserId, novel_id: NovelId) -> None:
        _execute(
            self._connection_factory,
            "DELETE FROM library_entries WHERE user_id = %s AND novel_id = %s",
            (str(user_id), str(novel_id)),
        )

    def list_by_user(self, user_id: UserId) -> list[LibraryEntry]:
        rows = _fetch_all(
            self._connection_factory,
            "SELECT user_id, novel_id, created_at FROM library_entries WHERE user_id = %s ORDER BY created_at DESC, novel_id ASC",
            (str(user_id),),
        )
        return [
            LibraryEntry(
                user_id=UserId(str(row["user_id"])),
                novel_id=NovelId(str(row["novel_id"])),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]


def _novel_from_row(row: dict[str, Any]) -> Novel:
    return Novel(
        id=NovelId(str(row["id"])),
        title=str(row["title"]),
        author=Author(
            id=UserId(str(row["author_id"])),
            display_name=str(row["author_display_name"]),
        ),
        cover_image_url=str(row["cover_image_url"] or ""),
        status=NovelStatus(str(row["status"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        owner_id=UserId(str(row["owner_id"])),
        isbn=str(row["isbn"]) if row.get("isbn") is not None else None,
        external_code=str(row["external_code"]) if row.get("external_code") is not None else None,
        last_modified_user_id=(
            UserId(str(row["last_modified_user_id"]))
            if row.get("last_modified_user_id") is not None
            else None
        ),
    )


def _execute(connection_factory: ConnectionFactory, query: str, params: tuple[Any, ...]) -> None:
    connection = connection_factory()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _fetch_all(connection_factory: ConnectionFactory, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    connection = connection_factory()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        return list(cursor.fetchall())
    finally:
        cursor.close()
        connection.close()
