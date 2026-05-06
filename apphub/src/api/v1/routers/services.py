from typing import Optional

from fastapi import APIRouter, Cookie, Path, Query

from src.schemas.coreServices import CoreServicesInventoryResponse, ServiceLogsQuery, ServiceLogsResponse
from src.schemas.errorResponse import ErrorResponse
from src.services.core_services import CoreServicesService
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME


router = APIRouter()
_core_services_service = CoreServicesService()


def _get_core_services_service() -> CoreServicesService:
    return _core_services_service


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
    limit: int = Query(default=200, ge=1, le=5000, description="Maximum number of matching recent lines to return"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    query = ServiceLogsQuery(keyword=keyword, level=level, time_range=time_range, limit=limit)
    return _get_core_services_service().get_service_logs(session_token=session_token, service_key=service_key, query=query)