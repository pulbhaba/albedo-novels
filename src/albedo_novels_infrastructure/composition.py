from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import os
from uuid import uuid4

from albedo_novels_core.application import ChapterContentUseCases, ChapterMetadataUseCases, NovelUseCases
from albedo_novels_core.application.ports import ContentStoragePort
from albedo_novels_infrastructure.aws.s3_content_storage import S3ContentStorage
from albedo_novels_infrastructure.http.application import RequestStrategy
from albedo_novels_infrastructure.http.strategies import build_strategies
from albedo_novels_infrastructure.persistence.file_content_storage import FileContentStorage
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


_LOCAL_LIBRARY = InMemoryLibraryRepository()
_LOCAL_CONTENT = InMemoryContentStorage()
_LOCAL_CHAPTERS = InMemoryChapterRepository()


def build_use_cases() -> NovelUseCases:
    return NovelUseCases(
        novels=dao_test(),
        library=_LOCAL_LIBRARY,
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


def build_content_use_cases(content_storage: ContentStoragePort | None = None) -> ChapterContentUseCases:
    return ChapterContentUseCases(
        novels=dao_test(),
        content=content_storage if content_storage is not None else _local_content_storage(),
        clock=SystemClock(),
    )


def build_chapter_metadata_use_cases() -> ChapterMetadataUseCases:
    return ChapterMetadataUseCases(
        novels=dao_test(),
        chapters=_LOCAL_CHAPTERS,
        ids=UuidIdGenerator(),
    )


def build_http_strategies(content_storage: ContentStoragePort | None = None) -> dict[str, RequestStrategy]:
    return build_strategies(
        build_use_cases(),
        build_content_use_cases(content_storage),
        build_chapter_metadata_use_cases(),
    )


def build_mysql_http_strategies(
    session_factory: SessionFactory | None = None,
    content_storage: ContentStoragePort | None = None,
) -> dict[str, RequestStrategy]:
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
        ChapterContentUseCases(
            novels=novels,
            content=content_storage if content_storage is not None else _s3_content_storage(),
            clock=SystemClock(),
        ),
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


@lru_cache(maxsize=1)
def _s3_content_storage() -> S3ContentStorage:
    """Reuse the S3 client across requests handled by the same Lambda runtime."""
    return S3ContentStorage.from_environment()


def _local_content_storage() -> ContentStoragePort:
    directory = os.getenv("NOVELS_CHAPTER_CONTENT_DIR", "").strip()
    if not directory:
        return _LOCAL_CONTENT
    return _file_content_storage(directory)


@lru_cache(maxsize=8)
def _file_content_storage(directory: str) -> FileContentStorage:
    return FileContentStorage(directory)


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class SystemClock:
    def utcnow_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()
