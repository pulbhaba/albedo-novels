from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import quote

import boto3

from albedo_novels_core.application.ports import ContentStoragePort
from albedo_novels_core.domain.models import (
    ChapterContent,
    ChapterContentMetadata,
    ChapterId,
    NovelId,
    UserId,
)
from albedo_novels_infrastructure.config import ChapterContentStorageConfig


class S3ContentStorage(ContentStoragePort):
    """Persist immutable chapter content versions as S3 objects."""

    def __init__(self, bucket_name: str, s3_client: Any | None = None) -> None:
        if not bucket_name:
            raise ValueError("An S3 bucket name is required for chapter content storage")
        self._bucket_name = bucket_name
        self._s3 = s3_client if s3_client is not None else boto3.client("s3")

    @classmethod
    def from_environment(cls, s3_client: Any | None = None) -> "S3ContentStorage":
        config = ChapterContentStorageConfig.from_environment()
        return cls(config.bucket_name, s3_client=s3_client)

    def save(self, content: ChapterContent) -> ChapterContent:
        key = self._version_key(content.novel_id, content.chapter_id, content.version)
        payload = {
            "novelId": str(content.novel_id),
            "chapterId": str(content.chapter_id),
            "version": content.version,
            "body": content.body,
            "createdAt": content.created_at,
            "createdBy": str(content.created_by),
        }
        self._s3.put_object(
            Bucket=self._bucket_name,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            ContentType="application/json",
            Metadata={
                "created-at": _encode_metadata(content.created_at),
                "created-by": _encode_metadata(str(content.created_by)),
            },
            IfNoneMatch="*",
        )
        return content

    def get_latest(self, novel_id: NovelId, chapter_id: ChapterId) -> ChapterContent | None:
        versions = self._list_version_numbers(novel_id, chapter_id)
        if not versions:
            return None
        return self.get_version(novel_id, chapter_id, max(versions))

    def get_version(self, novel_id: NovelId, chapter_id: ChapterId, version: int) -> ChapterContent | None:
        if version < 1:
            return None
        try:
            response = self._s3.get_object(
                Bucket=self._bucket_name,
                Key=self._version_key(novel_id, chapter_id, version),
            )
        except self._s3.exceptions.NoSuchKey:
            return None

        body = response["Body"]
        try:
            payload = json.loads(body.read().decode("utf-8"))
        finally:
            body.close()
        return ChapterContent(
            novel_id=NovelId(payload["novelId"]),
            chapter_id=ChapterId(payload["chapterId"]),
            version=int(payload["version"]),
            body=payload["body"],
            created_at=payload["createdAt"],
            created_by=UserId(payload["createdBy"]),
        )

    def list_versions(self, novel_id: NovelId, chapter_id: ChapterId) -> list[ChapterContentMetadata]:
        metadata: list[ChapterContentMetadata] = []
        for version in self._list_version_numbers(novel_id, chapter_id):
            response = self._s3.head_object(
                Bucket=self._bucket_name,
                Key=self._version_key(novel_id, chapter_id, version),
            )
            object_metadata = response.get("Metadata", {})
            metadata.append(
                ChapterContentMetadata(
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    version=version,
                    created_at=_decode_metadata(object_metadata["created-at"]),
                    created_by=UserId(_decode_metadata(object_metadata["created-by"])),
                )
            )
        return metadata

    def _list_version_numbers(self, novel_id: NovelId, chapter_id: ChapterId) -> list[int]:
        prefix = self._chapter_prefix(novel_id, chapter_id)
        versions: list[int] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket_name, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key", "")
                suffix = key[len(prefix):] if key.startswith(prefix) else ""
                if suffix.endswith(".json") and suffix[:-5].isdigit():
                    version = int(suffix[:-5])
                    if version > 0:
                        versions.append(version)
        return sorted(set(versions), reverse=True)

    @classmethod
    def _chapter_prefix(cls, novel_id: NovelId, chapter_id: ChapterId) -> str:
        encoded_novel_id = quote(str(novel_id), safe="")
        encoded_chapter_id = quote(str(chapter_id), safe="")
        return f"novels/{encoded_novel_id}/chapters/{encoded_chapter_id}/versions/"

    @classmethod
    def _version_key(cls, novel_id: NovelId, chapter_id: ChapterId, version: int) -> str:
        if version < 1:
            raise ValueError("Chapter content versions must be positive integers")
        return f"{cls._chapter_prefix(novel_id, chapter_id)}{version}.json"


def _encode_metadata(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _decode_metadata(value: str) -> str:
    return base64.b64decode(value.encode("ascii"), validate=True).decode("utf-8")
