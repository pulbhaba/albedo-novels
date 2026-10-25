from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from albedo_novels_core.domain.models import Novel, NovelId, NovelStatus, UserContext, UserId
from albedo_novels_infrastructure.composition import build_mysql_http_strategies
from albedo_novels_infrastructure.http import HttpApplication, HttpRequest
from albedo_novels_infrastructure.persistence.in_memory import InMemoryContentStorage
from albedo_novels_infrastructure.persistence.sqlalchemy import Base, SqlAlchemyNovelRepository


class _Authenticator:
    def __init__(self, user: UserContext) -> None:
        self._user = user

    def authenticate(self, headers: object) -> UserContext:
        return self._user


def test_mysql_http_composition_persists_chapters_using_sql_novel_authorization() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    novels = SqlAlchemyNovelRepository(sessions)
    novels.save(
        Novel(
            id=NovelId("persisted-novel"),
            title="Persisted novel",
            author_id=UserId("author-1"),
            status=NovelStatus.DRAFT,
            created_at="2026-10-18T00:00:00+00:00",
            updated_at="2026-10-18T00:00:00+00:00",
        )
    )
    owner = HttpApplication(
        _Authenticator(UserContext(UserId("author-1"))),
        build_mysql_http_strategies(sessions, content_storage=InMemoryContentStorage()),
    )

    created = owner.handle(
        HttpRequest(
            method="POST",
            path="/novels/persisted-novel/chapters",
            body={"title": "Opening"},
        )
    )
    listed_after_recomposition = HttpApplication(
        _Authenticator(UserContext(UserId("author-1"))),
        build_mysql_http_strategies(sessions, content_storage=InMemoryContentStorage()),
    ).handle(HttpRequest(method="GET", path="/novels/persisted-novel/chapters"))
    forbidden = HttpApplication(
        _Authenticator(UserContext(UserId("reader-1"))),
        build_mysql_http_strategies(sessions, content_storage=InMemoryContentStorage()),
    ).handle(HttpRequest(method="GET", path="/novels/persisted-novel/chapters"))

    assert created.status_code == 201
    assert created.body["displayOrder"] == 1
    assert listed_after_recomposition.status_code == 200
    assert listed_after_recomposition.body["items"] == [created.body]
    assert forbidden.status_code == 403


def test_mysql_http_composition_requires_s3_bucket_without_storage_override(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.delenv("NOVELS_CHAPTER_CONTENT_BUCKET", raising=False)

    with pytest.raises(ValueError, match="NOVELS_CHAPTER_CONTENT_BUCKET"):
        build_mysql_http_strategies(sessions)
