import asyncio
import base64
import json
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Cookie, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.schemas.hostAccess import (
    HostAccessConnectionTestResponse,
    HostAccessAttributesMutationResponse,
    HostAccessCopyItemRequest,
    HostAccessCreateFileRequest,
    HostAccessCreateFolderRequest,
    HostAccessDirectoryResponse,
    HostAccessDeleteItemRequest,
    HostAccessFilePreferences,
    HostAccessFilePreferencesUpdateRequest,
    HostAccessMutationResponse,
    HostAccessProfileResponse,
    HostAccessProfileUpsertRequest,
    HostAccessRenameItemRequest,
    HostAccessTextFileResponse,
    HostAccessUpdateAttributesRequest,
    HostAccessUploadRequest,
    HostAccessWriteTextRequest,
)
from src.services.host_access import HostAccessService
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME

router = APIRouter()
_host_access_service = HostAccessService()


def _get_host_access_service() -> HostAccessService:
    return _host_access_service


@router.get(
    "/host-access/profile",
    summary="Get current host access profile",
    description="Get the current local-host SSH profile bound to the authenticated product operator",
    responses={200: {"model": HostAccessProfileResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_host_access_profile(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().get_profile(session_token=session_token)


@router.put(
    "/host-access/profile",
    summary="Save and verify host access profile",
    description="Verify the local-host SSH credentials and save them for terminal and file access",
    responses={200: {"model": HostAccessProfileResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def save_host_access_profile(payload: HostAccessProfileUpsertRequest, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().save_profile(session_token=session_token, payload=payload.model_dump())


@router.post(
    "/host-access/profile/test",
    summary="Test host access profile",
    description="Verify the local-host SSH credentials without changing the saved login information",
    responses={200: {"model": HostAccessConnectionTestResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def test_host_access_profile(payload: HostAccessProfileUpsertRequest, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().test_profile(session_token=session_token, payload=payload.model_dump())


@router.delete(
    "/host-access/profile",
    summary="Clear host access profile",
    description="Delete the saved local-host SSH profile for the current authenticated operator",
    responses={200: {"model": HostAccessProfileResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def clear_host_access_profile(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().clear_profile(session_token=session_token)


@router.post(
    "/host-access/profiles/{profile_id}/activate",
    summary="Activate saved host access profile",
    description="Use a saved local-host login as the current runtime profile for terminal and file access",
    responses={200: {"model": HostAccessProfileResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def activate_host_access_profile(profile_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().activate_saved_profile(session_token=session_token, profile_id=profile_id)


@router.post(
    "/host-access/profiles/{profile_id}/test",
    summary="Test saved host access profile",
    description="Verify one saved host login without activating it",
    responses={200: {"model": HostAccessConnectionTestResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def test_saved_host_access_profile(profile_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().test_saved_profile(session_token=session_token, profile_id=profile_id)


@router.post(
    "/host-access/profiles/{profile_id}/default",
    summary="Set default host access profile",
    description="Mark one saved local-host login as the default profile for the current product operator",
    responses={200: {"model": HostAccessProfileResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def set_default_host_access_profile(profile_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().set_default_profile(session_token=session_token, profile_id=profile_id)


@router.delete(
    "/host-access/profiles/{profile_id}",
    summary="Delete saved host access profile",
    description="Delete one saved local-host login for the current product operator",
    responses={200: {"model": HostAccessProfileResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def delete_host_access_profile(profile_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_host_access_service().delete_saved_profile(session_token=session_token, profile_id=profile_id)


@router.put(
    "/host-access/preferences",
    summary="Update host access file preferences",
    description="Persist terminal file manager display preferences for the current authenticated operator",
    responses={200: {"model": HostAccessFilePreferences}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def update_host_access_preferences(
    payload: HostAccessFilePreferencesUpdateRequest,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().update_file_preferences(session_token=session_token, payload=payload.model_dump())


@router.get(
    "/host-access/files/tree",
    summary="List host directory contents",
    description="Browse the local host file system through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessDirectoryResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_host_access_tree(
    path: str = Query("/", description="Absolute host path"),
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().list_directory(session_token=session_token, path=path, profile_id=profile_id)


@router.get(
    "/host-access/files/content",
    summary="Read host text file content",
    description="Read a UTF-8 text file from the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessTextFileResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def read_host_access_text_content(
    path: str = Query(..., description="Absolute host file path"),
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().read_text_file(session_token=session_token, path=path, profile_id=profile_id)


@router.put(
    "/host-access/files/content",
    summary="Save host text file content",
    description="Save a UTF-8 text file on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def save_host_access_text_content(
    payload: HostAccessWriteTextRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().write_text_file(session_token=session_token, path=payload.path, content=payload.content, profile_id=profile_id)


@router.post(
    "/host-access/files/folders",
    summary="Create host directory",
    description="Create a directory on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_host_access_folder(
    payload: HostAccessCreateFolderRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().create_directory(session_token=session_token, parent_path=payload.parent_path, name=payload.name, profile_id=profile_id)


@router.post(
    "/host-access/files/items",
    summary="Create host file",
    description="Create an empty file on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_host_access_file(
    payload: HostAccessCreateFileRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().create_empty_file(session_token=session_token, parent_path=payload.parent_path, name=payload.name, profile_id=profile_id)


@router.post(
    "/host-access/files/rename",
    summary="Rename host file system entry",
    description="Rename a file or directory on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def rename_host_access_item(
    payload: HostAccessRenameItemRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().rename_item(session_token=session_token, source_path=payload.source_path, target_name=payload.target_name, profile_id=profile_id)


@router.delete(
    "/host-access/files/item",
    summary="Delete host file system entry",
    description="Delete a file or directory on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def delete_host_access_item(
    payload: HostAccessDeleteItemRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().delete_item(session_token=session_token, path=payload.path, profile_id=profile_id)


@router.post(
    "/host-access/files/copy",
    summary="Copy host file system entry",
    description="Copy a file or directory on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def copy_host_access_item(
    payload: HostAccessCopyItemRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().copy_item(
        session_token=session_token,
        source_path=payload.source_path,
        destination_path=payload.destination_path,
        profile_id=profile_id,
    )


@router.post(
    "/host-access/files/move",
    summary="Move host file system entry",
    description="Move a file or directory on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def move_host_access_item(
    payload: HostAccessCopyItemRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().move_item(
        session_token=session_token,
        source_path=payload.source_path,
        destination_path=payload.destination_path,
        profile_id=profile_id,
    )


@router.put(
    "/host-access/files/attributes",
    summary="Update host file system entry attributes",
    description="Update name, owner, group, and permissions for a file or directory on the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessAttributesMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def update_host_access_item_attributes(
    payload: HostAccessUpdateAttributesRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_host_access_service().update_item_attributes(session_token=session_token, payload=payload.model_dump(), profile_id=profile_id)


@router.get(
    "/host-access/files/download",
    summary="Download host file",
    description="Download a file from the local host through the saved SSH/SFTP profile",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def download_host_access_item(
    path: str = Query(..., description="Absolute host file path"),
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    payload = _get_host_access_service().download_file(session_token=session_token, path=path, profile_id=profile_id)
    response = StreamingResponse(BytesIO(payload["content"]), media_type=payload["media_type"])
    response.headers["Content-Disposition"] = f'attachment; filename="{payload["file_name"]}"'
    return response


@router.post(
    "/host-access/files/upload",
    summary="Upload host file",
    description="Upload a file to the local host through the saved SSH/SFTP profile",
    responses={200: {"model": HostAccessMutationResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def upload_host_access_file(
    payload: HostAccessUploadRequest,
    profile_id: Optional[str] = Query(None, description="Saved host profile identifier"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    try:
        file_payload = base64.b64decode(payload.content_base64.encode("utf-8"), validate=True)
    except Exception:
        raise CustomException(status_code=400, message="Invalid Request", details="content_base64 must be valid base64")
    return _get_host_access_service().upload_file(
        session_token=session_token,
        parent_path=payload.parent_path,
        file_name=payload.file_name,
        payload=file_payload,
        profile_id=profile_id,
    )


@router.websocket("/host-access/terminal/ws")
async def host_access_terminal_ws(websocket: WebSocket):
    await websocket.accept()
    service = _get_host_access_service()
    session_token = websocket.cookies.get(PRODUCT_AUTH_COOKIE_NAME)
    session_id = str(websocket.query_params.get("session_id") or "")
    try:
        cols = int(websocket.query_params.get("cols", "120"))
        rows = int(websocket.query_params.get("rows", "32"))
        attached = service.attach_terminal_session(session_token=session_token, session_id=session_id, cols=cols, rows=rows)
        profile = attached["profile"]
        snapshot = str(attached.get("buffer") or "")
        output_cursor = int(attached.get("cursor") or 0)
    except CustomException as exc:
        await websocket.send_json({"type": "error", "message": exc.message, "details": exc.details})
        await websocket.close(code=4400)
        return
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": "Terminal Bridge Error", "details": str(exc)})
        await websocket.close(code=1011)
        return

    async def pump_output():
        cursor = output_cursor
        try:
            while True:
                updates, next_cursor, closed = service.read_terminal_updates(session_id=session_id, after_cursor=cursor)
                if updates:
                    for payload in updates:
                        try:
                            await websocket.send_text(json.dumps({"type": "output", "session_id": session_id, "data": payload}))
                        except RuntimeError:
                            return
                    cursor = next_cursor
                    continue
                if closed:
                    break
                await asyncio.sleep(0.02)
        finally:
            try:
                await websocket.send_text(json.dumps({"type": "closed", "session_id": session_id}))
            except RuntimeError:
                pass

    output_task = asyncio.create_task(pump_output())
    await websocket.send_text(json.dumps({"type": "ready", "session_id": session_id, "cwd": profile["working_directory"], "username": profile["username"]}))
    if snapshot:
        await websocket.send_text(json.dumps({"type": "output", "session_id": session_id, "data": snapshot}))
    try:
        while True:
            payload = await websocket.receive_text()
            try:
                message = json.loads(payload)
            except json.JSONDecodeError:
                message = {"type": "input", "data": payload}

            if message.get("type") == "input":
                service.send_terminal_input(session_id=session_id, data=str(message.get("data") or ""))
                continue

            if message.get("type") == "resize":
                cols_value = max(int(message.get("cols") or cols), 40)
                rows_value = max(int(message.get("rows") or rows), 10)
                service.resize_terminal_session(session_id=session_id, cols=cols_value, rows=rows_value)
                continue

            if message.get("type") == "terminate":
                service.terminate_terminal_session(session_token=session_token, session_id=session_id)
                continue
    except WebSocketDisconnect:
        pass
    finally:
        output_task.cancel()
        service.detach_terminal_session(session_id=session_id)
