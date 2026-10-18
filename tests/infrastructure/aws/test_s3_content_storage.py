from __future__ import annotations

from datetime import datetime, timezone
import io
import json

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber
import pytest

from albedo_novels_core.domain.models import ChapterContent, ChapterId, NovelId, UserId
from albedo_novels_infrastructure.aws.s3_content_storage import S3ContentStorage
from albedo_novels_infrastructure.config import ChapterContentStorageConfig


BUCKET = "novel-content-test-bucket"


def _client():
    return boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="test-access-key",
        aws_secret_access_key="test-secret-key",
    )


def _content(version: int = 1) -> ChapterContent:
    return ChapterContent(
        novel_id=NovelId("novel-1"),
        chapter_id=ChapterId("chapter-1"),
        version=version,
        body="A chapter body",
        created_at="2026-10-18T00:00:00+00:00",
        created_by=UserId("author-1"),
    )


def _key(version: int) -> str:
    return f"novels/novel-1/chapters/chapter-1/versions/{version}.json"


def _list_response(versions: list[int]) -> dict[str, object]:
    return {
        "IsTruncated": False,
        "Name": BUCKET,
        "Prefix": "novels/novel-1/chapters/chapter-1/versions/",
        "KeyCount": len(versions),
        "Contents": [
            {"Key": _key(version), "Size": 10, "StorageClass": "STANDARD"}
            for version in versions
        ],
    }


def _stored_body(version: int) -> StreamingBody:
    payload = {
        "novelId": "novel-1",
        "chapterId": "chapter-1",
        "version": version,
        "body": "A chapter body",
        "createdAt": "2026-10-18T00:00:00+00:00",
        "createdBy": "author-1",
    }
    data = json.dumps(payload).encode("utf-8")
    return StreamingBody(io.BytesIO(data), len(data))


def _head_response() -> dict[str, object]:
    return {
        "LastModified": datetime(2026, 10, 18, tzinfo=timezone.utc),
        "ContentLength": 100,
        "ETag": '"version-etag"',
        "Metadata": {"created-at": "MjAyNi0xMC0xOFQwMDowMDowMCswMDowMA==", "created-by": "YXV0aG9yLTE="},
    }


def test_save_writes_one_immutable_version_with_author_and_timestamp_metadata() -> None:
    client = _client()
    content = _content()
    stubber = Stubber(client)
    stubber.add_response(
        "put_object",
        {"ETag": '"stored-etag"'},
        {
            "Bucket": BUCKET,
            "Key": _key(1),
            "Body": json.dumps(
                {
                    "novelId": "novel-1",
                    "chapterId": "chapter-1",
                    "version": 1,
                    "body": "A chapter body",
                    "createdAt": "2026-10-18T00:00:00+00:00",
                    "createdBy": "author-1",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            "ContentType": "application/json",
            "Metadata": {"created-at": "MjAyNi0xMC0xOFQwMDowMDowMCswMDowMA==", "created-by": "YXV0aG9yLTE="},
            "IfNoneMatch": "*",
        },
    )

    with stubber:
        assert S3ContentStorage(BUCKET, client).save(content) == content


def test_get_latest_reads_highest_version_using_numeric_order() -> None:
    client = _client()
    stubber = Stubber(client)
    prefix = "novels/novel-1/chapters/chapter-1/versions/"
    stubber.add_response(
        "list_objects_v2",
        _list_response([2, 10]),
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    stubber.add_response(
        "get_object",
        {"Body": _stored_body(10), "ContentLength": 150},
        {"Bucket": BUCKET, "Key": _key(10)},
    )

    with stubber:
        latest = S3ContentStorage(BUCKET, client).get_latest(
            NovelId("novel-1"),
            ChapterId("chapter-1"),
        )

    assert latest == _content(10)


def test_list_versions_returns_metadata_newest_first() -> None:
    client = _client()
    stubber = Stubber(client)
    prefix = "novels/novel-1/chapters/chapter-1/versions/"
    stubber.add_response(
        "list_objects_v2",
        _list_response([1, 10, 2]),
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    for version in [10, 2, 1]:
        stubber.add_response("head_object", _head_response(), {"Bucket": BUCKET, "Key": _key(version)})

    with stubber:
        versions = S3ContentStorage(BUCKET, client).list_versions(NovelId("novel-1"), ChapterId("chapter-1"))

    assert [item.version for item in versions] == [10, 2, 1]
    assert versions[0].created_at == "2026-10-18T00:00:00+00:00"
    assert versions[0].created_by == UserId("author-1")


def test_missing_content_returns_none_or_empty_list() -> None:
    client = _client()
    stubber = Stubber(client)
    prefix = "novels/novel-1/chapters/chapter-1/versions/"
    stubber.add_response("list_objects_v2", _list_response([]), {"Bucket": BUCKET, "Prefix": prefix})
    stubber.add_response("list_objects_v2", _list_response([]), {"Bucket": BUCKET, "Prefix": prefix})
    stubber.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        service_message="The specified key does not exist.",
        http_status_code=404,
        expected_params={"Bucket": BUCKET, "Key": _key(1)},
    )

    storage = S3ContentStorage(BUCKET, client)
    with stubber:
        assert storage.get_latest(NovelId("novel-1"), ChapterId("chapter-1")) is None
        assert storage.list_versions(NovelId("novel-1"), ChapterId("chapter-1")) == []
        assert storage.get_version(NovelId("novel-1"), ChapterId("chapter-1"), 1) is None


def test_bucket_configuration_is_required_and_validated() -> None:
    with pytest.raises(ValueError, match="NOVELS_CHAPTER_CONTENT_BUCKET"):
        ChapterContentStorageConfig.from_environment({})

    with pytest.raises(ValueError, match="valid S3 bucket name"):
        ChapterContentStorageConfig.from_environment({"NOVELS_CHAPTER_CONTENT_BUCKET": "192.168.1.1"})
    with pytest.raises(ValueError, match="valid S3 bucket name"):
        ChapterContentStorageConfig.from_environment({"NOVELS_CHAPTER_CONTENT_BUCKET": "Invalid-bucket"})
    with pytest.raises(ValueError, match="valid S3 bucket name"):
        ChapterContentStorageConfig.from_environment({"NOVELS_CHAPTER_CONTENT_BUCKET": "novel-.bucket"})

    assert ChapterContentStorageConfig.from_environment(
        {"NOVELS_CHAPTER_CONTENT_BUCKET": BUCKET}
    ).bucket_name == BUCKET
