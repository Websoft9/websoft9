from fastapi import APIRouter, Query
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

@router.put("/settings")
def update_settings():
    return {"settings": "settings"}