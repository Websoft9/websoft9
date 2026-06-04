import asyncio
import hashlib
import json
from typing import Any, Optional

from fastapi import APIRouter, Cookie, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from src.core.logger import logger
from src.schemas.coreServices import CoreServicesInventoryResponse, ServiceLogsQuery, ServiceLogsResponse
from src.schemas.errorResponse import ErrorResponse
from src.services.core_services import CoreServicesService
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME


router = APIRouter()
_core_services_service = CoreServicesService()


def _get_core_services_service() -> CoreServicesService:
    return _core_services_service


def _build_service_logs_response(session_token: Optional[str], service_key: str, query: ServiceLogsQuery) -> ServiceLogsResponse:
    return _get_core_services_service().get_service_logs(session_token=session_token, service_key=service_key, query=query)


def _serialize_stream_snapshot(payload: dict[str, Any]) -> tuple[str, str]:
    event_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(event_json.encode("utf-8")).hexdigest()
    return digest, event_json


@router.get(
    "/services",
    summary="List bundled core services",
    description="Return bundled third-party service state, health, indicators, and navigation metadata.",
    responses={200: {"model": CoreServicesInventoryResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_core_services(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return CoreServicesInventoryResponse(services=_get_core_services_service().list_services(session_token=session_token))


@router.get(
    "/services/{service_key}/logs",
    summary="Query service raw logs",
    description="Return recent raw logs for one bundled third-party service.",
    responses={200: {"model": ServiceLogsResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_service_logs(
    service_key: str = Path(..., description="Supported service key"),
    keyword: Optional[str] = Query(default=None, description="Case-insensitive keyword filter"),
    level: Optional[str] = Query(default=None, description="Optional log level filter: info, warning, error, fatal"),
    time_range: str = Query(default="all", description="Optional time range filter: all, 15m, 1h, 6h, 24h, 7d"),
    limit: int = Query(default=200, ge=1, le=20000, description="Maximum number of matching recent lines to return"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    query = ServiceLogsQuery(keyword=keyword, level=level, time_range=time_range, limit=limit)
    return _build_service_logs_response(session_token=session_token, service_key=service_key, query=query)


@router.get(
    "/services/{service_key}/logs/stream",
    summary="Stream service raw logs",
    description="Server-sent events stream for recent bundled third-party service logs.",
    responses={200: {"description": "Service logs stream established"}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def stream_service_logs(
    request: Request,
    service_key: str = Path(..., description="Supported service key"),
    keyword: Optional[str] = Query(default=None, description="Case-insensitive keyword filter"),
    level: Optional[str] = Query(default=None, description="Optional log level filter: info, warning, error, fatal"),
    time_range: str = Query(default="all", description="Optional time range filter: all, 15m, 1h, 6h, 24h, 7d"),
    limit: int = Query(default=200, ge=1, le=20000, description="Maximum number of matching recent lines to return"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    query = ServiceLogsQuery(keyword=keyword, level=level, time_range=time_range, limit=limit)

    async def event_generator():
        refresh_seconds = 5.0
        stream_cursor = None

        while True:
            if await request.is_disconnected():
                break

            try:
                if stream_cursor is None:
                    response, stream_cursor = _get_core_services_service().open_service_logs_stream(
                        session_token=session_token,
                        service_key=service_key,
                        query=query,
                    )
                    payload = {
                        "logs": jsonable_encoder(response),
                        "refresh_hint_ms": int(refresh_seconds * 1000),
                    }
                    _digest, event_json = _serialize_stream_snapshot(payload)
                    yield f"retry: {int(refresh_seconds * 1000)}\n"
                    yield f"event: snapshot\ndata: {event_json}\n\n"
                else:
                    delta = _get_core_services_service().poll_service_logs_stream(session_token=session_token, cursor=stream_cursor)
                    if delta.snapshot is not None:
                        refresh_seconds = 5.0
                        payload = {
                            "logs": jsonable_encoder(delta.snapshot),
                            "refresh_hint_ms": int(refresh_seconds * 1000),
                        }
                        _digest, event_json = _serialize_stream_snapshot(payload)
                        yield f"retry: {int(refresh_seconds * 1000)}\n"
                        yield f"event: snapshot\ndata: {event_json}\n\n"
                    elif delta.entries:
                        refresh_seconds = 5.0
                        payload = {
                            "append": {
                                "service": service_key,
                                "limit": query.limit,
                                "entries": jsonable_encoder(delta.entries),
                            },
                            "refresh_hint_ms": int(refresh_seconds * 1000),
                        }
                        _digest, event_json = _serialize_stream_snapshot(payload)
                        yield f"retry: {int(refresh_seconds * 1000)}\n"
                        yield f"event: append\ndata: {event_json}\n\n"
                    else:
                        refresh_seconds = min(refresh_seconds + 2.5, 15.0)
                        yield ": keep-alive\n\n"
            except Exception as exc:
                logger.warning(f"Service logs stream failed for {service_key}: {exc}")
                payload = json.dumps({"message": "Service logs stream refresh failed"}, separators=(",", ":"))
                yield f"event: error\ndata: {payload}\n\n"
                refresh_seconds = min(refresh_seconds + 2.5, 15.0)

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