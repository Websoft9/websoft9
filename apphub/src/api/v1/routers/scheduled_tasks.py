import asyncio
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Cookie, Query, Request, Response
from fastapi.responses import StreamingResponse

from src.schemas.errorResponse import ErrorResponse
from src.schemas.scheduledTasks import ScheduledTaskToggleRequest, ScheduledTaskWriteRequest
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME
from src.services.scheduled_tasks import ScheduledTaskService


router = APIRouter()
_scheduled_task_service = ScheduledTaskService()


def _get_scheduled_task_service() -> ScheduledTaskService:
    return _scheduled_task_service


@router.get("/scheduled-tasks", responses={200: {"model": dict}, 401: {"model": ErrorResponse}})
def list_scheduled_tasks(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().list_tasks(session_token)


@router.post("/scheduled-tasks/sync", status_code=202, responses={401: {"model": ErrorResponse}})
def sync_scheduled_tasks(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().start_sync(session_token)


@router.get("/scheduled-tasks/stream", responses={200: {"description": "Scheduled task stream established"}, 401: {"model": ErrorResponse}})
async def stream_scheduled_tasks(request: Request, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    async def event_generator():
        last_digest: Optional[str] = None
        while not await request.is_disconnected():
            snapshot = _get_scheduled_task_service().list_cached_tasks(session_token)
            payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if digest != last_digest:
                last_digest = digest
                yield f"event: snapshot\ndata: {payload}\n\n"
            else:
                yield ": keep-alive\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.post("/scheduled-tasks/hosts/{profile_id}/capability", responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def check_scheduled_task_host_capability(profile_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().check_host_capability(session_token, profile_id)


@router.post("/scheduled-tasks", status_code=201, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
def create_scheduled_task(payload: ScheduledTaskWriteRequest, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().create_task(session_token, payload.model_dump())


@router.put("/scheduled-tasks/{task_id}", responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def update_scheduled_task(task_id: str, payload: ScheduledTaskWriteRequest, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().update_task(session_token, task_id, payload.model_dump())


@router.post("/scheduled-tasks/{task_id}/toggle", responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def toggle_scheduled_task(task_id: str, payload: ScheduledTaskToggleRequest, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().toggle_task(session_token, task_id, payload.enabled)


@router.delete("/scheduled-tasks/{task_id}", status_code=204, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def delete_scheduled_task(task_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    _get_scheduled_task_service().delete_task(session_token, task_id)
    return Response(status_code=204)


@router.post("/scheduled-tasks/{task_id}/run", status_code=202, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def run_scheduled_task(task_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().run_task(session_token, task_id)


@router.post("/scheduled-tasks/{task_id}/refresh-status", responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def refresh_scheduled_task_status(task_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().refresh_status(session_token, task_id)


@router.get("/scheduled-tasks/{task_id}/runs", responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def list_scheduled_task_runs(task_id: str, offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100), session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().list_runs(session_token, task_id, offset, limit)


@router.get("/scheduled-tasks/{task_id}/runs/{run_id}/log", responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def get_scheduled_task_run_log(task_id: str, run_id: str, before: Optional[int] = Query(default=None, ge=0), session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return _get_scheduled_task_service().get_run_log(session_token, task_id, run_id, before)


@router.get("/scheduled-tasks/{task_id}/runs/{run_id}/log/download", responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def download_scheduled_task_run_log(task_id: str, run_id: str, session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    content = _get_scheduled_task_service().download_run_log(session_token, task_id, run_id)
    filename = f"scheduled-task-{task_id}-{run_id}.log"
    return Response(content=content, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})