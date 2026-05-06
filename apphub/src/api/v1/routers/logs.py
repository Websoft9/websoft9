from typing import Optional

from fastapi import APIRouter, Cookie, Query

from src.schemas.errorResponse import ErrorResponse
from src.schemas.runtimeLogs import RuntimeLogsQuery, RuntimeLogsResponse, RuntimeLogsSourcesResponse
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME
from src.services.runtime_logs import RuntimeLogsService


router = APIRouter()
_runtime_logs_service = RuntimeLogsService()


def _get_runtime_logs_service() -> RuntimeLogsService:
    return _runtime_logs_service


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
    entries = _get_runtime_logs_service().get_runtime_logs(session_token=session_token, query=query)
    return RuntimeLogsResponse(source="runtime-console", level=query.level, keyword=query.keyword, time_range=query.time_range, limit=query.limit, entries=entries)