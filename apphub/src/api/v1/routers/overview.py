from typing import Optional

from fastapi import APIRouter, Cookie

from src.schemas.errorResponse import ErrorResponse
from src.schemas.overview import OverviewResponse
from src.services.overview_service import OverviewService
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME


router = APIRouter()
_overview_service = OverviewService()


def _get_overview_service() -> OverviewService:
    return _overview_service


@router.get(
    "/overview",
    summary="Get homepage overview summary",
    description="Return the product-native home overview summary for the dashboard route.",
    responses={200: {"model": OverviewResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_overview(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return _get_overview_service().get_overview(session_token=session_token)
