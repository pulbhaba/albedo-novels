from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import os
from uuid import uuid4

from albedo_novels_core.application import ChapterContentUseCases, ChapterMetadataUseCases, NovelUseCases
from albedo_novels_infrastructure.persistence.in_memory import (
    InMemoryChapterRepository,
    InMemoryContentStorage,
    InMemoryLibraryRepository,
)
from albedo_novels_infrastructure.persistence.seeded_novel_dao import dao_test
from albedo_novels_infrastructure.persistence.sqlalchemy import (
    SessionFactory,
    SqlAlchemyChapterRepository,
    SqlAlchemyLibraryRepository,
    SqlAlchemyNovelRepository,
)
from albedo_novels_infrastructure.http.application import RequestStrategy
from albedo_novels_infrastructure.http.strategies import build_strategies


_LOCAL_LIBRARY = InMemoryLibraryRepository()
_LOCAL_CONTENT = InMemoryContentStorage()
_LOCAL_CHAPTERS = InMemoryChapterRepository()


def _repositories() -> tuple[object, object]:
    return dao_test(), _LOCAL_CONTENT


def build_use_cases() -> NovelUseCases:
    return NovelUseCases(
        novels=dao_test(),
        library=_LOCAL_LIBRARY,
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


def build_content_use_cases() -> ChapterContentUseCases:
    novels, content = _repositories()
    return ChapterContentUseCases(novels=novels, content=content, clock=SystemClock())


def build_chapter_metadata_use_cases() -> ChapterMetadataUseCases:
    return ChapterMetadataUseCases(
        novels=dao_test(),
        chapters=_LOCAL_CHAPTERS,
        ids=UuidIdGenerator(),
    )


def build_http_strategies() -> dict[str, RequestStrategy]:
    return build_strategies(build_use_cases(), build_content_use_cases(), build_chapter_metadata_use_cases())


def build_mysql_http_strategies(session_factory: SessionFactory | None = None) -> dict[str, RequestStrategy]:
    """Build Lambda HTTP strategies with SQL-backed novel and chapter metadata."""
    sessions = session_factory or _mysql_session_factory()
    novels = SqlAlchemyNovelRepository(sessions)
    return build_strategies(
        NovelUseCases(
            novels=novels,
            library=SqlAlchemyLibraryRepository(sessions),
            ids=UuidIdGenerator(),
            clock=SystemClock(),
        ),
        ChapterContentUseCases(novels=novels, content=_LOCAL_CONTENT, clock=SystemClock()),
        ChapterMetadataUseCases(
            novels=novels,
            chapters=SqlAlchemyChapterRepository(sessions),
            ids=UuidIdGenerator(),
        ),
    )


def build_mysql_use_cases() -> NovelUseCases:
    """Build use cases backed by SQLAlchemy and the configured MySQL database."""
    sessions = _mysql_session_factory()
    return NovelUseCases(
        novels=SqlAlchemyNovelRepository(sessions),
        library=SqlAlchemyLibraryRepository(sessions),
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


def build_mysql_chapter_metadata_use_cases() -> ChapterMetadataUseCases:
    """Build chapter metadata use cases backed by the configured MySQL database."""
    sessions = _mysql_session_factory()
    return ChapterMetadataUseCases(
        novels=SqlAlchemyNovelRepository(sessions),
        chapters=SqlAlchemyChapterRepository(sessions),
        ids=UuidIdGenerator(),
    )


@lru_cache(maxsize=1)
def _mysql_session_factory() -> SessionFactory:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("NOVELS_DB_URL", "mysql+mysqlconnector://root:test_pass@localhost:3306/auth"))
    return sessionmaker(bind=engine, expire_on_commit=False)


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class SystemClock:
    def utcnow_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()
