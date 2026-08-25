from __future__ import annotations

from datetime import datetime, timezone
import os
from uuid import uuid4

from albedo_novels_core.application import ChapterContentUseCases, NovelUseCases
from albedo_novels_infrastructure.persistence.in_memory import InMemoryContentStorage, InMemoryLibraryRepository
from albedo_novels_infrastructure.persistence.seeded_novel_dao import dao_test
from albedo_novels_infrastructure.persistence.sqlalchemy import SqlAlchemyLibraryRepository, SqlAlchemyNovelRepository


_LOCAL_LIBRARY = InMemoryLibraryRepository()
_LOCAL_CONTENT = InMemoryContentStorage()


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


def build_mysql_use_cases() -> NovelUseCases:
    """Build use cases backed by SQLAlchemy and the configured MySQL database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.getenv("NOVELS_DB_URL", "mysql+mysqlconnector://root:test_pass@localhost:3306/auth"))
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return NovelUseCases(
        novels=SqlAlchemyNovelRepository(sessions),
        library=SqlAlchemyLibraryRepository(sessions),
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class SystemClock:
    def utcnow_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()
