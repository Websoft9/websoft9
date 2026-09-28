import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Cookie, Query, Request
from fastapi.responses import StreamingResponse

from src.core.logger import logger
from src.schemas.errorResponse import ErrorResponse
from src.schemas.overview import OverviewResponse
from src.services.overview_service import OverviewService
from src.services.overview_stream_cache import overview_stream_cache
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME


router = APIRouter()
_overview_service = OverviewService()


def _get_overview_service() -> OverviewService:
    return _overview_service


def _normalize_locale(value: Optional[str]) -> str:
    """Map the console language onto the two published App Store catalogues.

    Any other value falls back to English, which is also what the store itself serves.
    """
    return "zh" if str(value or "").strip().lower().startswith("zh") else "en"


@router.get(
    "/overview",
    summary="Get homepage overview summary",
    description="Return the product-native home overview summary for the dashboard route.",
    responses={200: {"model": OverviewResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_overview(
    locale: Optional[str] = Query(
        default=None, description="Console language (zh/en); decides which App Store catalogue is counted"
    ),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return overview_stream_cache.get_overview(
        session_token=session_token,
        locale=_normalize_locale(locale),
        force_refresh=True,
    )


@router.get(
    "/overview/stream",
    summary="Stream homepage overview summary",
    description="Server-sent events stream for dashboard overview snapshots.",
    responses={200: {"description": "Overview stream established"}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def stream_overview(
    request: Request,
    locale: Optional[str] = Query(
        default=None, description="Console language (zh/en); decides which App Store catalogue is counted"
    ),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    normalized_locale = _normalize_locale(locale)

    async def event_generator():
        last_digest: str | None = None

        while True:
            if await request.is_disconnected():
                break

            sleep_seconds = 10.0

            try:
                snapshot = await asyncio.to_thread(
                    overview_stream_cache.get_snapshot,
                    session_token,
                    locale=normalized_locale,
                    force_refresh=last_digest is None,
                )
                sleep_seconds = min(max(snapshot.refresh_interval_seconds, 1.0), 10.0)

                if snapshot.digest != last_digest:
                    last_digest = snapshot.digest
                    yield f"retry: {int(snapshot.refresh_interval_seconds * 1000)}\n"
                    yield f"event: snapshot\ndata: {snapshot.event_json}\n\n"
                else:
                    yield ": keep-alive\n\n"
            except Exception as exc:
                logger.warning(f"Overview stream failed: {exc}")
                payload = json.dumps({"message": "Overview stream refresh failed"}, separators=(",", ":"))
                yield f"event: error\ndata: {payload}\n\n"

            await asyncio.sleep(sleep_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
