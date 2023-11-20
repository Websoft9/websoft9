from fastapi import APIRouter, Query,Path
from src.schemas.appSettings import AppSettings
from src.schemas.errorResponse import ErrorResponse

from src.services.settings_manager import SettingsManager

router = APIRouter()

@router.get("/settings",
            summary="Get settings",
            description="Get settings",
            responses={
                200: {"model": AppSettings},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def get_settings():
    return SettingsManager().read_all()

@router.get(
            "/settings/{section}",
            summary="Get settings",
            description="Get settings by section",
            responses={
                200: {"model": AppSettings},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def get_setting_by_section(
    section: str = Path(..., description="Section name to update settings from"),
):
    return SettingsManager().read_section(section)

@router.put(
            "/settings/{section}",
            summary="Update Settings",
            description="Update settings",
            responses={
                200: {"model": AppSettings},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def update_settings(
    section: str = Path(..., description="Section name to update settings from"),
    key: str = Query(..., description="Key name to update settings from"),
    value: str = Query(..., description="Key value to update settings from"),
):
    return SettingsManager().write_section(section,key,value)