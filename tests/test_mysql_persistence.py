from __future__ import annotations

from albedo_novels_core.domain.models import LibraryEntry, NovelId, UserId
from albedo_novels_infrastructure.persistence.mysql import MySqlLibraryRepository, MySqlNovelRepository


class FakeCursor:
    def __init__(self, connection: "FakeConnection", rows: list[dict[str, object]]) -> None:
        self.connection = connection
        self.rows = rows
        self.executed: tuple[str, tuple[object, ...]] | None = None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.executed = (query, params)
        self.connection.queries.append(self.executed)

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows

    def close(self) -> None:
        return None


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = rows or []
        self.queries: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.closed = False

    def cursor(self, **_kwargs: object) -> FakeCursor:
        return FakeCursor(self, self.rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FailingCursor(FakeCursor):
    def execute(self, query: str, params: tuple[object, ...]) -> None:
        super().execute(query, params)
        raise RuntimeError("database failure")


class FailingConnection(FakeConnection):
    def cursor(self, **_kwargs: object) -> FailingCursor:
        return FailingCursor(self, self.rows)


def test_mysql_novel_repository_maps_metadata_rows() -> None:
    connection = FakeConnection(
        [
            {
                "id": "novel-1",
                "title": "The Title",
                "author_id": "user-1",
                "author_display_name": "Author",
                "cover_image_url": None,
                "status": "draft",
                "created_at": "2026-08-01T00:00:00+00:00",
                "updated_at": "2026-08-02T00:00:00+00:00",
                "owner_id": "user-1",
                "isbn": "978-1",
                "external_code": "catalog-1",
                "last_modified_user_id": "editor-1",
            }
        ]
    )
    repository = MySqlNovelRepository(lambda: connection)

    novel = repository.get(NovelId("novel-1"))

    assert novel is not None
    assert novel.title == "The Title"
    assert novel.cover_image_url == ""
    assert novel.isbn == "978-1"
    assert novel.external_code == "catalog-1"
    assert novel.last_modified_user_id == UserId("editor-1")
    assert connection.closed


def test_mysql_repositories_write_and_read_library_entries() -> None:
    connection = FakeConnection(
        [{"user_id": "user-1", "novel_id": "novel-1", "created_at": "2026-08-01T00:00:00+00:00"}]
    )
    repository = MySqlLibraryRepository(lambda: connection)
    entry = LibraryEntry(UserId("user-1"), NovelId("novel-1"), "2026-08-01T00:00:00+00:00")

    assert repository.save(entry) == entry
    assert repository.list_by_user(UserId("user-1")) == [entry]
    repository.delete(UserId("user-1"), NovelId("novel-1"))

    assert connection.commits == 2
    assert len(connection.queries) == 3
    assert "library_entries" in connection.queries[0][0]


def test_mysql_write_rolls_back_and_closes_resources_on_failure() -> None:
    connection = FailingConnection()
    repository = MySqlLibraryRepository(lambda: connection)
    entry = LibraryEntry(UserId("user-1"), NovelId("novel-1"), "now")

    try:
        repository.save(entry)
    except RuntimeError as error:
        assert str(error) == "database failure"
    else:
        raise AssertionError("save should propagate database failures")

    assert connection.commits == 0
    assert connection.closed
