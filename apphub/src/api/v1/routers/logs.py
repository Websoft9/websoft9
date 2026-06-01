import asyncio
import hashlib
import json
from typing import Any, Optional

from fastapi import APIRouter, Cookie, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from src.core.logger import logger
from src.schemas.errorResponse import ErrorResponse
from src.schemas.runtimeLogs import RuntimeLogsQuery, RuntimeLogsResponse, RuntimeLogsSourcesResponse
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME
from src.services.runtime_logs import RuntimeLogsService


router = APIRouter()
_runtime_logs_service = RuntimeLogsService()


def _get_runtime_logs_service() -> RuntimeLogsService:
    return _runtime_logs_service


def _build_runtime_logs_response(session_token: Optional[str], query: RuntimeLogsQuery) -> RuntimeLogsResponse:
    entries = _get_runtime_logs_service().get_runtime_logs(session_token=session_token, query=query)
    return RuntimeLogsResponse(source="runtime-console", level=query.level, keyword=query.keyword, time_range=query.time_range, limit=query.limit, entries=entries)


def _serialize_stream_snapshot(payload: dict[str, Any]) -> tuple[str, str]:
    event_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(event_json.encode("utf-8")).hexdigest()
    return digest, event_json


@router.get(
    "/logs/sources",
    summary="List runtime log sources",
    description="List the curated runtime log sources exposed by Websoft9.",
    responses={200: {"model": RuntimeLogsSourcesResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_runtime_log_sources(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return {"sources": _get_runtime_logs_service().list_sources(session_token=session_token)}


@router.get(
    "/logs/runtime",
    summary="Query runtime console logs",
    description="Return curated Websoft9 runtime-console logs from the current product container.",
    responses={200: {"model": RuntimeLogsResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_runtime_logs(
    level: Optional[str] = Query(default=None, description="Severity filter: error, warning, info"),
    keyword: Optional[str] = Query(default=None, description="Case-insensitive keyword filter"),
    time_range: Optional[str] = Query(default=None, description="Time range filter: 15m, 1h, 6h, 24h"),
    limit: int = Query(default=200, ge=1, le=1000, description="Maximum number of matching recent lines to return"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    query = RuntimeLogsQuery(level=level, keyword=keyword, time_range=time_range, limit=limit)
    return _build_runtime_logs_response(session_token=session_token, query=query)


@router.get(
    "/logs/runtime/stream",
    summary="Stream runtime console logs",
    description="Server-sent events stream for curated Websoft9 runtime-console logs.",
    responses={200: {"description": "Runtime logs stream established"}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def stream_runtime_logs(
    request: Request,
    level: Optional[str] = Query(default=None, description="Severity filter: error, warning, info"),
    keyword: Optional[str] = Query(default=None, description="Case-insensitive keyword filter"),
    time_range: Optional[str] = Query(default=None, description="Time range filter: 15m, 1h, 6h, 24h"),
    limit: int = Query(default=200, ge=1, le=1000, description="Maximum number of matching recent lines to return"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    query = RuntimeLogsQuery(level=level, keyword=keyword, time_range=time_range, limit=limit)

    async def event_generator():
        last_digest: Optional[str] = None
        refresh_seconds = 5.0

        while True:
            if await request.is_disconnected():
                break

            try:
                response = _build_runtime_logs_response(session_token=session_token, query=query)
                payload = {
                    "logs": jsonable_encoder(response),
                    "refresh_hint_ms": int(refresh_seconds * 1000),
                }
                digest, event_json = _serialize_stream_snapshot(payload)

                if digest != last_digest:
                    last_digest = digest
                    yield f"retry: {int(refresh_seconds * 1000)}\n"
                    yield f"event: snapshot\ndata: {event_json}\n\n"
                else:
                    yield ": keep-alive\n\n"
            except Exception as exc:
                logger.warning(f"Runtime logs stream failed: {exc}")
                payload = json.dumps({"message": "Runtime logs stream refresh failed"}, separators=(",", ":"))
                yield f"event: error\ndata: {payload}\n\n"

            await asyncio.sleep(refresh_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )