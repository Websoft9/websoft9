from typing import Optional

from fastapi import APIRouter, Cookie, Path, Query

from src.core.exception import CustomException
from src.schemas.appVolumeBrowse import AppVolumeBrowseContentResponse, AppVolumeBrowseTreeResponse
from src.schemas.errorResponse import ErrorResponse
from src.services.app_volume_browse import AppVolumeBrowseService
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME


router = APIRouter()
_service = AppVolumeBrowseService()


def _get_service() -> AppVolumeBrowseService:
    return _service


@router.get(
    "/myapps/{app_id}/volumes/{volume_id}/browse/tree",
    summary="Browse an application volume",
    description="Read-only directory browsing for a volume mounted by the current application's running containers",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    response_model=AppVolumeBrowseTreeResponse,
)
def browse_application_volume_tree(
    app_id: str = Path(..., min_length=1, max_length=256),
    volume_id: str = Path(..., min_length=1, max_length=256),
    path: str = Query("/", max_length=4096),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_service().list_directory(session_token, app_id, volume_id, path)


@router.get(
    "/myapps/{app_id}/volumes/{volume_id}/browse/content",
    summary="Preview an application volume text file",
    description="Read-only UTF-8 text preview for a file in a volume mounted by the current application's running containers",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    response_model=AppVolumeBrowseContentResponse,
)
def browse_application_volume_content(
    app_id: str = Path(..., min_length=1, max_length=256),
    volume_id: str = Path(..., min_length=1, max_length=256),
    path: str = Query(..., min_length=1, max_length=4096),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_service().read_text_file(session_token, app_id, volume_id, path)