from __future__ import annotations

from typing import Any, Mapping

from albedo_novels_core.application import (
    ChapterContentUseCases,
    ConflictError,
    CreateNovelCommand,
    ForbiddenError,
    ListNovelsQuery,
    NotFoundError,
    NovelUseCases,
    UpdateNovelCommand,
)
from albedo_novels_core.domain.models import (
    ChapterContent,
    ChapterContentMetadata,
    ChapterId,
    LibraryEntry,
    LibraryNovel,
    Novel,
    NovelId,
    NovelStatus,
    UserContext,
    UserId,
)

from .application import DEFAULT_LIMIT, MAX_LIMIT, HttpRequest, HttpResponse, RequestStrategy


class HealthStrategy:
    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        return HttpResponse(200, {"status": "ok", "service": "albedo-novel-service"})


class ListNovelsStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        limit = _coerce_int(request.query.get("limit"), DEFAULT_LIMIT, maximum=MAX_LIMIT)
        offset = _coerce_int(request.query.get("offset"), 0, minimum=0)
        page = self._use_cases.list_novels(ListNovelsQuery(limit=limit, offset=offset))
        return HttpResponse(
            200,
            {
                "items": [novel_to_dict(novel) for novel in page.items],
                "total": page.total,
                "limit": page.limit,
                "offset": page.offset,
            },
        )


class CreateNovelStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        command, error = _create_novel_command(request.body)
        if error is not None:
            return _validation_error(error)
        assert command is not None
        assert user is not None
        novel = self._use_cases.create_novel(
            user,
            CreateNovelCommand(title=command.title, author_id=user.user_id, isbn=command.isbn),
        )
        return HttpResponse(201, novel_to_dict(novel))


class GetNovelStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        assert user is not None
        try:
            novel = self._use_cases.get_novel(user, NovelId(_novel_id(request, path_params)))
        except NotFoundError as error:
            return _error_response(404, "not_found", error)
        except ForbiddenError as error:
            return _error_response(403, "forbidden", error)
        return HttpResponse(200, novel_to_dict(novel))


class UpdateDraftStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        command, error = _update_novel_command(request.body)
        if error is not None:
            return _validation_error(error)
        assert command is not None
        assert user is not None
        try:
            novel = self._use_cases.update_draft(user, NovelId(_novel_id(request, path_params)), command)
        except NotFoundError as error:
            return _error_response(404, "not_found", error)
        except ForbiddenError as error:
            return _error_response(403, "forbidden", error)
        except ConflictError as error:
            return _error_response(409, "conflict", error)
        return HttpResponse(200, novel_to_dict(novel))


class PublishNovelStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        assert user is not None
        try:
            novel = self._use_cases.publish_novel(user, NovelId(_novel_id(request, path_params)))
        except NotFoundError as error:
            return _error_response(404, "not_found", error)
        except ForbiddenError as error:
            return _error_response(403, "forbidden", error)
        except ConflictError as error:
            return _error_response(409, "conflict", error)
        return HttpResponse(200, novel_to_dict(novel))


class AddFavoriteStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        assert user is not None
        try:
            entry = self._use_cases.add_favorite(user, NovelId(_novel_id(request, path_params)))
        except NotFoundError as error:
            return _error_response(404, "not_found", error)
        except ForbiddenError as error:
            return _error_response(403, "forbidden", error)
        return HttpResponse(200, library_entry_to_dict(entry))


class RemoveFavoriteStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        assert user is not None
        self._use_cases.remove_favorite(user, NovelId(_novel_id(request, path_params)))
        return HttpResponse(204, {})


class ListLibraryStrategy:
    def __init__(self, use_cases: NovelUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        assert user is not None
        return HttpResponse(
            200,
            {"items": [library_novel_to_dict(item) for item in self._use_cases.list_library(user)]},
        )


class GetChapterStrategy:
    def __init__(self, use_cases: ChapterContentUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        assert user is not None
        try:
            ids = ChapterIds.from_params(path_params)
            content = self._use_cases.get_latest(user, ids.novel, ids.chapter)
        except NotFoundError as error:
            return _error_response(404, "not_found", error)
        except ForbiddenError as error:
            return _error_response(403, "forbidden", error)
        return HttpResponse(200, chapter_content_to_dict(content))


class ListChapterVersionsStrategy:
    def __init__(self, use_cases: ChapterContentUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        assert user is not None
        ids = ChapterIds.from_params(path_params)
        try:
            versions = self._use_cases.list_versions(user, ids.novel, ids.chapter)
        except NotFoundError as error:
            return _error_response(404, "not_found", error)
        except ForbiddenError as error:
            return _error_response(403, "forbidden", error)
        return HttpResponse(200, {"items": [chapter_metadata_to_dict(item) for item in versions]})


class WriteChapterStrategy:
    def __init__(self, use_cases: ChapterContentUseCases) -> None:
        self._use_cases = use_cases

    def handle(self, request: HttpRequest, user: UserContext | None, path_params: Mapping[str, str]) -> HttpResponse:
        body, error = _chapter_body(request.body)
        if error is not None:
            return _validation_error(error)
        assert body is not None
        assert user is not None
        ids = ChapterIds.from_params(path_params)
        try:
            content = self._use_cases.write(user, ids.novel, ids.chapter, body)
        except NotFoundError as error:
            return _error_response(404, "not_found", error)
        except ForbiddenError as error:
            return _error_response(403, "forbidden", error)
        return HttpResponse(201, chapter_content_to_dict(content))


class ChapterIds:
    def __init__(self, novel: NovelId, chapter: ChapterId) -> None:
        self.novel = novel
        self.chapter = chapter

    @classmethod
    def from_params(cls, path_params: Mapping[str, str]) -> ChapterIds:
        return cls(NovelId(path_params["novel_id"]), ChapterId(path_params["chapter_id"]))


def build_strategies(
    use_cases: NovelUseCases,
    content_use_cases: ChapterContentUseCases | None = None,
) -> dict[str, RequestStrategy]:
    strategies: dict[str, RequestStrategy] = {
        "health": HealthStrategy(),
        "list_novels": ListNovelsStrategy(use_cases),
        "create_novel": CreateNovelStrategy(use_cases),
        "get_novel": GetNovelStrategy(use_cases),
        "update_draft": UpdateDraftStrategy(use_cases),
        "publish_novel": PublishNovelStrategy(use_cases),
        "list_library": ListLibraryStrategy(use_cases),
        "add_favorite": AddFavoriteStrategy(use_cases),
        "remove_favorite": RemoveFavoriteStrategy(use_cases),
    }
    if content_use_cases is not None:
        strategies.update(
            {
                "get_chapter": GetChapterStrategy(content_use_cases),
                "list_chapter_versions": ListChapterVersionsStrategy(content_use_cases),
                "write_chapter": WriteChapterStrategy(content_use_cases),
            }
        )
    return strategies


def _error_response(status: int, error_name: str, error: Exception) -> HttpResponse:
    return HttpResponse(status, {"error": error_name, "message": str(error)})


def _validation_error(message: str) -> HttpResponse:
    return HttpResponse(400, {"error": "validation_error", "message": message})


def _novel_id(request: HttpRequest, path_params: Mapping[str, str]) -> str:
    return path_params.get("novel_id") or request.path.rsplit("/", 1)[-1]


def _coerce_int(value: object, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    if minimum is not None and parsed < minimum:
        return minimum
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed


def novel_to_dict(novel: Novel) -> dict[str, Any]:
    return {
        "id": novel.id,
        "title": novel.title,
        "authorId": novel.author_id,
        "isbn": novel.isbn,
        "status": novel.status.value if isinstance(novel.status, NovelStatus) else str(novel.status),
        "createdAt": novel.created_at,
        "updatedAt": novel.updated_at,
    }


def _create_novel_command(body: object) -> tuple[CreateNovelCommand | None, str | None]:
    if not isinstance(body, Mapping):
        return None, "Request body must be a JSON object."
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, "title is required and must be a non-empty string."
    if len(title) > 255:
        return None, "title must be 255 characters or fewer."
    isbn = body.get("isbn")
    if isbn is not None and (not isinstance(isbn, str) or not isbn.strip() or len(isbn) > 32):
        return None, "isbn must be a non-empty string of 32 characters or fewer."
    return CreateNovelCommand(title=title, author_id=UserId(""), isbn=isbn), None


def _update_novel_command(body: object) -> tuple[UpdateNovelCommand | None, str | None]:
    if not isinstance(body, Mapping):
        return None, "Request body must be a JSON object."
    if "title" not in body and "isbn" not in body:
        return None, "At least one of title or isbn must be provided."
    title = body.get("title")
    if "title" in body and (not isinstance(title, str) or not title.strip()):
        return None, "title must be a non-empty string."
    if isinstance(title, str) and len(title) > 255:
        return None, "title must be 255 characters or fewer."
    isbn = body.get("isbn")
    if "isbn" in body and isbn is not None and (not isinstance(isbn, str) or not isbn.strip() or len(isbn) > 32):
        return None, "isbn must be null or a non-empty string of 32 characters or fewer."
    return UpdateNovelCommand(title=title, isbn=isbn, update_isbn="isbn" in body), None


def library_entry_to_dict(entry: LibraryEntry) -> dict[str, Any]:
    return {"novelId": entry.novel_id, "createdAt": entry.created_at}


def library_novel_to_dict(item: LibraryNovel) -> dict[str, Any]:
    return {"novel": novel_to_dict(item.novel), "favoritedAt": item.favorited_at}


def chapter_content_to_dict(content: ChapterContent) -> dict[str, Any]:
    return {**chapter_metadata_to_dict(content.metadata()), "body": content.body}


def chapter_metadata_to_dict(content: ChapterContentMetadata) -> dict[str, Any]:
    return {
        "novelId": content.novel_id,
        "chapterId": content.chapter_id,
        "version": content.version,
        "createdAt": content.created_at,
        "createdBy": content.created_by,
    }


def _chapter_body(body: object) -> tuple[str | None, str | None]:
    if not isinstance(body, Mapping):
        return None, "Request body must be a JSON object."
    content = body.get("body")
    if not isinstance(content, str) or not content:
        return None, "body is required and must be a non-empty string."
    return content, None
