from fastapi import APIRouter, Query

from src.schemas.errorResponse import ErrorResponse
from src.services.appstore_sync_manager import AppStoreSyncManager

router = APIRouter()


@router.post(
    "/appstore/sync",
    summary="Sync App Store Assets",
    description="Synchronize App Store static assets into the local runtime and refresh local browse payloads.",
    responses={
        200: {"model": dict},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def sync_appstore_assets(
    channel: str | None = Query(None, description="Optional artifact channel override", regex="^(release|rc|dev)$"),
    package_types: str | None = Query(None, description="Comma-separated package types to sync, for example media,library"),
    force_refresh: bool = Query(False, description="Force a full sync even when incremental update checks can skip unchanged packages"),
):
    return AppStoreSyncManager().sync(
        trigger="manual",
        channel=channel,
        package_types=package_types,
        force_refresh=force_refresh,
    )


@router.get(
    "/appstore/state",
    summary="Get App Store Sync State",
    description="Return the current local App Store sync state, including last sync time and active dataset version.",
    responses={
        200: {"model": dict},
        500: {"model": ErrorResponse},
    },
)
def get_appstore_state():
    return AppStoreSyncManager().get_state()


@router.get(
    "/appstore/sync/status",
    summary="Get App Store Sync Running Status",
    description="Check whether a background sync is currently running.",
    responses={
        200: {"model": dict},
        500: {"model": ErrorResponse},
    },
)
def get_appstore_sync_status():
    return AppStoreSyncManager().get_sync_status()


@router.get(
    "/appstore/versions",
    summary="List App Store Dataset Versions",
    description="List locally available App Store dataset versions from the snapshot release history.",
    responses={
        200: {"model": dict},
        500: {"model": ErrorResponse},
    },
)
def list_appstore_versions():
    return AppStoreSyncManager().list_versions()


@router.post(
    "/appstore/activate",
    summary="Activate App Store Dataset Version",
    description="Activate a locally available App Store dataset version from the snapshot releases.",
    responses={
        200: {"model": dict},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def activate_appstore_version(
    dataset_version: str = Query(..., description="Dataset version to activate from local releases"),
):
    return AppStoreSyncManager().activate(dataset_version=dataset_version, trigger="manual")
