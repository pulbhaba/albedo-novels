from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from albedo_novels_core.application.ports import ContentStoragePort
from albedo_novels_core.domain.models import (
    ChapterContent,
    ChapterContentMetadata,
    ChapterId,
    NovelId,
    UserId,
)


class FileContentStorage(ContentStoragePort):
    """Persist immutable chapter content versions as JSON files."""

    def __init__(self, directory: str | Path) -> None:
        directory_value = str(directory).strip()
        if not directory_value:
            raise ValueError("A chapter content directory is required")
        self._root = Path(directory_value).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, content: ChapterContent) -> ChapterContent:
        version_directory = self._versions_directory(content.novel_id, content.chapter_id)
        version_directory.mkdir(parents=True, exist_ok=True)
        destination = version_directory / self._version_filename(content.version)
        payload = json.dumps(
            {
                "novelId": str(content.novel_id),
                "chapterId": str(content.chapter_id),
                "version": content.version,
                "body": content.body,
                "createdAt": content.created_at,
                "createdBy": str(content.created_by),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=version_directory,
                prefix=".chapter-content-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            # A hard link publishes the complete file atomically and fails if
            # this immutable version already exists.
            os.link(temporary_path, destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return content

    def get_latest(self, novel_id: NovelId, chapter_id: ChapterId) -> ChapterContent | None:
        versions = self._version_numbers(novel_id, chapter_id)
        if not versions:
            return None
        return self.get_version(novel_id, chapter_id, versions[0])

    def get_version(self, novel_id: NovelId, chapter_id: ChapterId, version: int) -> ChapterContent | None:
        if version < 1:
            return None
        path = self._versions_directory(novel_id, chapter_id) / self._version_filename(version)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

        return ChapterContent(
            novel_id=NovelId(payload["novelId"]),
            chapter_id=ChapterId(payload["chapterId"]),
            version=int(payload["version"]),
            body=payload["body"],
            created_at=payload["createdAt"],
            created_by=UserId(payload["createdBy"]),
        )

    def list_versions(self, novel_id: NovelId, chapter_id: ChapterId) -> list[ChapterContentMetadata]:
        return [
            content.metadata()
            for version in self._version_numbers(novel_id, chapter_id)
            if (content := self.get_version(novel_id, chapter_id, version)) is not None
        ]

    def _version_numbers(self, novel_id: NovelId, chapter_id: ChapterId) -> list[int]:
        version_directory = self._versions_directory(novel_id, chapter_id)
        if not version_directory.is_dir():
            return []
        versions = {
            int(path.stem)
            for path in version_directory.glob("*.json")
            if path.stem.isdecimal() and int(path.stem) > 0
        }
        return sorted(versions, reverse=True)

    def _versions_directory(self, novel_id: NovelId, chapter_id: ChapterId) -> Path:
        return (
            self._root
            / "novels"
            / _encode_path_component(str(novel_id))
            / "chapters"
            / _encode_path_component(str(chapter_id))
            / "versions"
        )

    @staticmethod
    def _version_filename(version: int) -> str:
        if version < 1:
            raise ValueError("Chapter content versions must be positive integers")
        return f"{version}.json"


def _encode_path_component(value: str) -> str:
    if not value:
        raise ValueError("Novel and chapter identifiers must not be empty")
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
