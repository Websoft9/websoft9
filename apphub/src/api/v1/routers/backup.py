from fastapi import APIRouter, Query, Path, Body
from typing import Dict, List
from src.schemas.errorResponse import ErrorResponse
from src.services.back_manager import BackupManager
from src.schemas.backupsnapshot import BackupSnapshot

router = APIRouter()

@router.post(
    "/backup/{app_id}",
    summary="Create Backup",
    description="Create a backup for the specified app",
    responses={
        200: {"description": "Backup created successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def create_backup(
    app_id: str = Path(..., description="App ID to create backup for")
):
    BackupManager().create_backup(app_id)
    return {"message": f"Backup created successfully for app: {app_id}"}

@router.get(
    "/backup/snapshots",
    summary="List Snapshots",
    description="List all snapshots or filter by app ID",
    responses={
        200: {"model": List[BackupSnapshot]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def list_snapshots(
    app_id: str = Query(None, description="App ID to filter snapshots by (optional)"),
):
    snapshots = BackupManager().list_snapshots(app_id)
    return snapshots

@router.delete(
    "/backup/snapshots/{snapshot_id}",
    summary="Delete Snapshot",
    description="Delete a snapshot by its ID",
    status_code=204,
    responses={
        204: {"description": "Snapshot deleted successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def delete_snapshot(
    snapshot_id: str = Path(..., description="Snapshot ID to delete"),
):
    BackupManager().delete_snapshot(snapshot_id)
    return {"message": f"Snapshot {snapshot_id} deleted successfully"}

@router.post(
    "/backup/restore/{app_id}/{snapshot_id}",
    summary="Restore Snapshot",
    description="Restore a snapshot to the specified locations",
    responses={
        200: {"description": "Snapshot restored successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def restore_snapshot(
    app_id: str = Path(..., description="App ID to restore"),
    snapshot_id: str = Path(..., description="Snapshot ID to restore")
):
    BackupManager().restore_backup(app_id,snapshot_id)
    return {"message": f"Snapshot {snapshot_id} restored successfully"}
