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
    force_refresh: bool = Query(True, description="Force the sync even when local marker files already exist"),
):
    return AppStoreSyncManager().sync(
        trigger="manual",
        channel=channel,
        package_types=package_types,
        force_refresh=force_refresh,
    )


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
