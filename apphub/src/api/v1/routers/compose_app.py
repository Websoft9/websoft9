"""
Router: /compose-apps

Dedicated lifecycle management API for custom Docker Compose applications.
These are separate from the marketplace (/apps) endpoints because:
  - Update flow: edit compose.yml in Gitea → redeploy (no catalog involved)
  - Remove flow: permanently deletes the user-owned Gitea repository
  - Redeploy: pulls from Gitea without catalog version tracking
  - Start/Stop/Restart: same Portainer operations but scoped to compose apps only
"""
from fastapi import APIRouter, Path, Query

from src.core.exception import CustomException
from src.schemas.appResponse import AppResponse
from src.schemas.composeApp import ComposeContentResponse, ComposeRedeployRequest, ComposeUpdateRequest
from src.schemas.errorResponse import ErrorResponse
from src.services.compose_app_manager import ComposeAppManager

router = APIRouter()

# ── List / Detail ──────────────────────────────────────────────────────────────

@router.get(
    "/compose-apps",
    summary="List Custom Compose Apps",
    description="List all installed custom Docker Compose applications (W9_DIST=compose).",
    responses={
        200: {"model": list[AppResponse]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def list_compose_apps(
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
    locale: str = Query("en", description="Language for app media resolution", regex="^(zh|en)(-[A-Za-z]{2})?$"),
):
    return ComposeAppManager().list_compose_apps(endpointId, locale)


@router.get(
    "/compose-apps/{app_id}",
    summary="Get Custom Compose App",
    description="Retrieve details for a single custom Docker Compose application.",
    responses={
        200: {"model": AppResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def get_compose_app(
    app_id: str = Path(..., description="Compose app ID"),
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
    locale: str = Query("en", description="Language for app media resolution", regex="^(zh|en)(-[A-Za-z]{2})?$"),
):
    return ComposeAppManager().get_compose_app(app_id, endpointId, locale)


@router.get(
    "/compose-apps/{app_id}/content",
    summary="Get Compose Content",
    description="Read docker-compose.yml, user environment variables, and mount files from the app's Gitea repository.",
    responses={
        200: {"model": ComposeContentResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def get_compose_content(
    app_id: str = Path(..., description="Compose app ID"),
):
    return ComposeAppManager().get_compose_content(app_id)


# ── Start / Stop / Restart ─────────────────────────────────────────────────────

@router.post(
    "/compose-apps/{app_id}/start",
    summary="Start Compose App",
    description="Start all containers of a custom compose application.",
    status_code=204,
    responses={
        204: {"description": "App started successfully"},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def start_compose_app(
    app_id: str = Path(..., description="Compose app ID"),
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
):
    ComposeAppManager().start_compose_app(app_id, endpointId)


@router.post(
    "/compose-apps/{app_id}/stop",
    summary="Stop Compose App",
    description="Stop all containers of a custom compose application.",
    status_code=204,
    responses={
        204: {"description": "App stopped successfully"},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def stop_compose_app(
    app_id: str = Path(..., description="Compose app ID"),
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
):
    ComposeAppManager().stop_compose_app(app_id, endpointId)


@router.post(
    "/compose-apps/{app_id}/restart",
    summary="Restart Compose App",
    description="Restart all containers of a custom compose application.",
    status_code=204,
    responses={
        204: {"description": "App restarted successfully"},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def restart_compose_app(
    app_id: str = Path(..., description="Compose app ID"),
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
):
    ComposeAppManager().restart_compose_app(app_id, endpointId)


# ── Redeploy ───────────────────────────────────────────────────────────────────

@router.post(
    "/compose-apps/{app_id}/redeploy",
    summary="Redeploy Compose App",
    description="Redeploy the compose application from its existing Gitea repository without modifying compose content.",
    status_code=204,
    responses={
        204: {"description": "Redeploy triggered successfully"},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def redeploy_compose_app(
    payload: ComposeRedeployRequest,
    app_id: str = Path(..., description="Compose app ID"),
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
):
    ComposeAppManager().redeploy_compose_app(app_id, endpointId, payload.pull_image)


# ── Update compose content ─────────────────────────────────────────────────────

@router.put(
    "/compose-apps/{app_id}/content",
    summary="Update Compose Content",
    description=(
        "Push updated docker-compose.yml, environment variables, and mount files to the app's "
        "Gitea repository, then trigger a Portainer redeploy from the updated repository. "
        "Internal W9_* environment variables are preserved automatically."
    ),
    status_code=204,
    responses={
        204: {"description": "Compose content updated and redeploy triggered"},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def update_compose_content(
    payload: ComposeUpdateRequest,
    app_id: str = Path(..., description="Compose app ID"),
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
):
    ComposeAppManager().update_compose_content(
        app_id,
        payload.compose_content,
        [e.model_dump() for e in payload.env],
        [m.model_dump() for m in payload.mounts],
        endpointId,
    )


# ── Remove ─────────────────────────────────────────────────────────────────────

@router.delete(
    "/compose-apps/{app_id}",
    summary="Remove Compose App",
    description=(
        "Permanently remove a custom compose application: stops all containers, "
        "removes the Portainer stack and all associated volumes, and deletes the Gitea repository. "
        "This operation cannot be undone."
    ),
    status_code=204,
    responses={
        204: {"description": "Compose app removed successfully"},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def remove_compose_app(
    app_id: str = Path(..., description="Compose app ID"),
    endpointId: int = Query(None, description="Portainer endpoint ID. Defaults to local endpoint."),
):
    ComposeAppManager().remove_compose_app(app_id, endpointId)
