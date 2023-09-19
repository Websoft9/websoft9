from fastapi import APIRouter, Query
from src.schemas.appInstall import appInstall
from src.schemas.errorResponse import ErrorResponse
from src.services.app_manager import AppManger

router = APIRouter(prefix="/api/v1")


@router.get("/apps/")
def get_apps():
    return {"apps": []}


@router.post(
    "/apps/install",
    summary="Install App",
    response_model_exclude_defaults=True, 
    description="Install an app on an endpoint",
    responses={
        200: {"description": "Success"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
def apps_install(
    appInstall: appInstall,
    endpointId: int = Query(None, description="Endpoint ID to install app on,if not set, install on the local endpoint"),
):
    appManger = AppManger()
    appManger.install_app(appInstall, endpointId)