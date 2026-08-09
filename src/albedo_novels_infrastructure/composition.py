from __future__ import annotations

from datetime import datetime, timezone
import os
from uuid import uuid4

from albedo_novels_core.application import NovelUseCases
from albedo_novels_infrastructure.persistence.seeded_novel_dao import dao_test
from albedo_novels_infrastructure.persistence import MySqlLibraryRepository, MySqlNovelRepository


def build_use_cases() -> NovelUseCases:
    return NovelUseCases(
        novels=dao_test(),
        library=EmptyLibraryRepository(),
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


def build_mysql_use_cases() -> NovelUseCases:
    """Build production use cases using the MySQL persistence adapters."""
    import mysql.connector

    def connection_factory():
        return mysql.connector.connect(
            host=os.getenv("NOVELS_DB_HOST", "localhost"),
            port=int(os.getenv("NOVELS_DB_PORT", "3306")),
            database=os.getenv("NOVELS_DB_NAME", "auth"),
            user=os.getenv("NOVELS_DB_USER", "root"),
            password=os.getenv("NOVELS_DB_PASSWORD", "test_pass"),
        )

    return NovelUseCases(
        novels=MySqlNovelRepository(connection_factory),
        library=MySqlLibraryRepository(connection_factory),
        ids=UuidIdGenerator(),
        clock=SystemClock(),
    )


class EmptyLibraryRepository:
    """Local-only stand-in for the production library repository."""

    def save(self, entry: object) -> object:
        return entry

    def delete(self, _user_id: object, _novel_id: object) -> None:
        return None

    def list_by_user(self, _user_id: object) -> list[object]:
        return []


class UuidIdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


class SystemClock:
    def utcnow_iso(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()
