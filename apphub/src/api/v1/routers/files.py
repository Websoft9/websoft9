import base64
from typing import Optional

from fastapi import APIRouter, Body, Cookie, Query
from fastapi.responses import Response

from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.schemas.fileManager import (
    FileManagerAttributesMutationResponse,
    FileManagerCopyItemRequest,
    FileManagerCreateFileRequest,
    FileManagerCreateFolderRequest,
    FileManagerDeleteRequest,
    FileManagerDirectoryResponse,
    FileManagerMetadataResponse,
    FileManagerMutationResponse,
    FileManagerRenameRequest,
    FileManagerTextFileResponse,
    FileManagerUpdateAttributesRequest,
    FileManagerUploadRequest,
    FileManagerVolumesResponse,
    FileManagerWriteTextRequest,
)
from src.services.file_manager import FileManagerService
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME

router = APIRouter()
_file_manager_service = FileManagerService()


def _get_file_manager_service() -> FileManagerService:
    return _file_manager_service


@router.get(
    "/files/volumes",
    summary="List approved Docker volumes",
    description="List the Docker volumes available at the logical file-manager root",
    responses={200: {"model": FileManagerVolumesResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_file_manager_volumes(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return {"volumes": _get_file_manager_service().list_volumes(session_token=session_token)}


@router.get(
    "/files/tree",
    summary="List Docker volume directory contents",
    description="List directory contents inside a selected Docker volume scope",
    responses={200: {"model": FileManagerDirectoryResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_file_manager_tree(
    volume_id: str = Query(..., description="Docker volume name"),
    path: str = Query("/", description="Relative path inside the selected volume"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().list_directory(session_token=session_token, volume_id=volume_id, relative_path=path)


@router.get(
    "/files/metadata",
    summary="Read file or directory metadata",
    description="Read metadata for a file-system item inside a selected Docker volume",
    responses={200: {"model": FileManagerMetadataResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def read_file_manager_metadata(
    volume_id: str = Query(..., description="Docker volume name"),
    path: str = Query("/", description="Relative path inside the selected volume"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().get_metadata(session_token=session_token, volume_id=volume_id, relative_path=path)


@router.get(
    "/files/root-tree",
    summary="List Docker volumes root directory contents",
    description="List directory contents for the logical /var/lib/docker/volumes root presented by the file manager",
    responses={200: {"model": FileManagerDirectoryResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_file_manager_root_tree(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().get_root_directory(session_token=session_token)


@router.get(
    "/files/root-metadata",
    summary="Read logical root metadata",
    description="Read metadata for the logical Docker volumes root presented by the file manager",
    responses={200: {"model": FileManagerMetadataResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def read_file_manager_root_metadata(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().get_root_metadata(session_token=session_token)


@router.get(
    "/files/content",
    summary="Read text file content",
    description="Read a UTF-8 text file from a selected Docker volume",
    responses={200: {"model": FileManagerTextFileResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def read_file_manager_text_content(
    volume_id: str = Query(..., description="Docker volume name"),
    path: str = Query(..., description="Relative file path inside the selected volume"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().read_text_file(session_token=session_token, volume_id=volume_id, relative_path=path)


@router.put(
    "/files/content",
    summary="Save text file content",
    description="Save UTF-8 text content inside a selected Docker volume",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def save_file_manager_text_content(
    payload: FileManagerWriteTextRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().write_text_file(
        session_token=session_token,
        volume_id=payload.volume_id,
        relative_path=payload.path,
        content=payload.content,
    )


@router.post(
    "/files/folders",
    summary="Create folder",
    description="Create a folder inside a selected Docker volume",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_file_manager_folder(
    payload: FileManagerCreateFolderRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().create_directory(
        session_token=session_token,
        volume_id=payload.volume_id,
        parent_path=payload.parent_path,
        name=payload.name,
    )


@router.post(
    "/files/items",
    summary="Create empty file",
    description="Create an empty file inside a selected Docker volume",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_file_manager_item(
    payload: FileManagerCreateFileRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().create_empty_file(
        session_token=session_token,
        volume_id=payload.volume_id,
        parent_path=payload.parent_path,
        name=payload.name,
    )


@router.post(
    "/files/rename",
    summary="Rename file or folder",
    description="Rename a file-system item inside a selected Docker volume",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def rename_file_manager_item(
    payload: FileManagerRenameRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().rename_path(
        session_token=session_token,
        volume_id=payload.volume_id,
        source_path=payload.source_path,
        target_name=payload.target_name,
    )


@router.post(
    "/files/copy",
    summary="Copy file or folder",
    description="Copy a file-system item into another directory inside a selected Docker volume",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def copy_file_manager_item(
    payload: FileManagerCopyItemRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().copy_path(
        session_token=session_token,
        volume_id=payload.volume_id,
        source_path=payload.source_path,
        destination_path=payload.destination_path,
    )


@router.post(
    "/files/move",
    summary="Move file or folder",
    description="Move a file-system item into another directory inside a selected Docker volume",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def move_file_manager_item(
    payload: FileManagerCopyItemRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().move_path(
        session_token=session_token,
        volume_id=payload.volume_id,
        source_path=payload.source_path,
        destination_path=payload.destination_path,
    )


@router.put(
    "/files/attributes",
    summary="Update file or folder attributes",
    description="Update name, owner, group, and permissions for a file-system item inside a selected Docker volume",
    responses={200: {"model": FileManagerAttributesMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def update_file_manager_item_attributes(
    payload: FileManagerUpdateAttributesRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().update_attributes(
        session_token=session_token,
        volume_id=payload.volume_id,
        payload=payload.model_dump(),
    )


@router.delete(
    "/files/item",
    summary="Delete file or folder",
    description="Delete a file-system item inside a selected Docker volume",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def delete_file_manager_item(
    payload: FileManagerDeleteRequest = Body(...),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_file_manager_service().delete_path(
        session_token=session_token,
        volume_id=payload.volume_id,
        relative_path=payload.path,
    )


@router.post(
    "/files/upload",
    summary="Upload file",
    description="Upload a file into a selected Docker volume directory",
    responses={200: {"model": FileManagerMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def upload_file_manager_item(
    payload: FileManagerUploadRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    try:
        file_payload = base64.b64decode(payload.content_base64.encode("utf-8"), validate=True)
    except Exception:
        raise CustomException(status_code=400, message="Invalid Request", details="content_base64 must be valid base64")
    return _get_file_manager_service().upload_file(
        session_token=session_token,
        volume_id=payload.volume_id,
        parent_path=payload.parent_path,
        file_name=payload.file_name,
        payload=file_payload,
    )


@router.get(
    "/files/download",
    summary="Download file",
    description="Download a file from a selected Docker volume",
    responses={200: {"description": "Binary file response"}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def download_file_manager_item(
    volume_id: str = Query(..., description="Docker volume name"),
    path: str = Query(..., description="Relative file path inside the selected volume"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    file_name, payload = _get_file_manager_service().download_file(
        session_token=session_token,
        volume_id=volume_id,
        relative_path=path,
    )
    return Response(
        content=payload,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
