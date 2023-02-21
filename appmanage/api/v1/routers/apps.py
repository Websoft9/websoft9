from typing import Optional, List

from fastapi import APIRouter, status, Depends
from pydantic import BaseModel
from starlette.responses import JSONResponse

from api.model.generic import GenericMessage, GenericExceptionMessage
from api.model.app import App
from api.service import manage

router = APIRouter()

@router.get("", responses={status.HTTP_200_OK: {"model": List[App]}})
def list_my_apps(app_name: Optional[str] = None, status_code: Optional[int] = None,
                 status: Optional[str] = None):
    fields = {}
    if app_name:
        fields['name'] = app_name
    if status_code:
        fields['status_code'] = status_code
    if status:
        fields['status'] = status

    return manage.get_my_app()