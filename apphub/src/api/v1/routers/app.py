from fastapi import APIRouter, Query,Path
from src.schemas.appAvailable import AppAvailableResponse
from src.schemas.appCatalog import AppCatalogResponse
from src.schemas.appInstall import appInstall
from src.schemas.appResponse import AppResponse
from src.schemas.errorResponse import ErrorResponse
from src.services.app_manager import AppManger
from src.services.common_check import install_validate
from threading import Thread

router = APIRouter()

@router.get(
        "/apps/catalog/{locale}",
        summary="List Catalogs",
        description="List all app's catalogs",
        responses={
        200: {"model": list[AppCatalogResponse]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        }
    )
def get_catalog_apps(
    locale: str = Path(..., description="Language to get catalogs from", regex="^(zh|en)$"),
):
    return AppManger().get_catalog_apps(locale)

@router.get(
        "/apps/available/{locale}",
        summary="List Available Apps",
        description="List all available apps",
        responses={
        200: {"model": list[AppAvailableResponse]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        }
    )
def get_available_apps(
    locale: str = Path(..., description="Language to get available apps from", regex="^(zh|en)$"),
):
    return AppManger().get_available_apps(locale)

@router.get(
        "/apps",
        summary="List Installed Apps",
        description="List all installed apps",
        responses={
        200: {"model": list[AppResponse]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        }
    )
def get_apps(
    endpointId: int = Query(None, description="Endpoint ID to get apps from. If not set, get apps from the local endpoint")
):
    return AppManger().get_apps(endpointId)

@router.get(
        "/apps/{app_id}",
        summary="Inspect App",
        description="Retrieve details about an app",
        responses={
        200: {"model": AppResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
    )
def get_app_by_id(
    app_id: str = Path(..., description="App ID to get details from"),
    endpointId: int = Query(None, description="Endpoint ID to get app details from. If not set, get details from the local endpoint")
):
    return AppManger().get_app_by_id(app_id, endpointId)

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
    # install validate
    install_validate(appInstall,endpointId)
    # install app
    Thread(target=AppManger().install_app, args=(appInstall, endpointId)).start()
    # return success
    return ErrorResponse(
        status_code=200,
        message="Success",
        details="The app is installing and can be viewed through 'My Apps.'",
    )

@router.post(
    "/apps/{app_id}/start",
    summary="Start App",
    description="Start an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App started successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_start(
    app_id: str = Path(..., description="App ID to start"),
    endpointId: int = Query(None, description="Endpoint ID to start app on. If not set, start on the local endpoint")
):
    AppManger().start_app(app_id, endpointId)


@router.post(
    "/apps/{app_id}/stop",
    summary="Stop App",
    response_model_exclude_defaults=True, 
    description="Stop an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App stopped successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_stop(
    app_id: str = Path(..., description="App ID to stop"),
    endpointId: int = Query(None, description="Endpoint ID to stop app on. If not set, stop on the local endpoint"),
):
    AppManger().stop_app(app_id, endpointId)

@router.post(
    "/apps/{app_id}/restart",
    summary="Restart App",
    response_model_exclude_defaults=True, 
    description="Restart an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App restarted successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_restart(
    app_id: str = Path(..., description="App ID to restart"),
    endpointId: int = Query(None, description="Endpoint ID to Restart app on. If not set, Restart on the local endpoint"),
):
    AppManger().restart_app(app_id, endpointId)

@router.put(
    "/apps/{app_id}/redeploy",
    summary="Redeploy App",
    response_model_exclude_defaults=True, 
    description="Redeploy an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App redeploy successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_redeploy(
    app_id: str = Path(..., description="App ID to redeploy"),
    endpointId: int = Query(None, description="Endpoint ID to redeploy app on. If not set, redeploy on the local endpoint"),
    pullImage: bool = Query(..., description="Whether to pull the image when redeploying the app"),
):
    AppManger().redeploy_app(app_id, pullImage,endpointId)


@router.delete(
    "/apps/{app_id}/uninstall",
    summary="Uninstall App",
    description="Uninstall an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App uninstalled successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
def apps_uninstall(
    app_id: str=Path(..., description="App ID to uninstall"),
    endpointId: int = Query(None, description="Endpoint ID to uninstall app on,if not set, uninstall on the local endpoint"),
    purge_data: bool = Query(..., description="Whether to purge data when uninstalling the app")
):
    AppManger().uninstall_app(app_id,purge_data, endpointId)


@router.delete(
    "/apps/{app_id}/remove",
    summary="Remove App",
    response_model_exclude_defaults=True, 
    description="Remove an app on an endpoint where the app is empty(status is 'inactive')",
    status_code=204,
    responses={
        204: {"description": "App removed successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_remove(
    app_id: str = Path(..., description="App ID to remove"),
    endpointId: int = Query(None, description="Endpoint ID to remove app on. If not set, remove on the local endpoint"),
):
    AppManger().remove_app(app_id, endpointId)
