from typing import Optional

from fastapi import APIRouter, Cookie, Query

from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.schemas.setupWizard import (
    SetupWizardAppResponse,
    SetupWizardCompleteResponse,
    SetupWizardInstallAcceptedResponse,
    SetupWizardInstallRequest,
    SetupWizardInstallStatusResponse,
    SetupWizardPlatformInitCompleteResponse,
    SetupWizardStateResponse,
)
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME
from src.services.setup_wizard import SetupWizardService

router = APIRouter()


@router.get(
    "/setup-wizard/state",
    summary="Get setup wizard state",
    responses={200: {"model": SetupWizardStateResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_setup_wizard_state(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    service = SetupWizardService()
    service.require_enabled()
    return service.get_state(session_token=session_token)


@router.get(
    "/setup-wizard/app",
    summary="Get marketplace app metadata",
    responses={200: {"model": SetupWizardAppResponse}, 400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_setup_wizard_app(
    locale: str = Query("en", regex="^(zh|en)(-[A-Za-z]{2})?$"),
):
    service = SetupWizardService()
    service.require_enabled()
    return service.get_app(locale)


@router.post(
    "/setup-wizard/platform-init-complete",
    summary="Advance setup wizard after platform initialization",
    responses={200: {"model": SetupWizardPlatformInitCompleteResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def complete_platform_initialization(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    service = SetupWizardService()
    service.require_enabled()
    return service.mark_platform_init_complete(session_token=session_token)


@router.post(
    "/setup-wizard/install",
    summary="Start marketplace app installation",
    responses={200: {"model": SetupWizardInstallAcceptedResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def install_marketplace_app(
    payload: SetupWizardInstallRequest,
    endpointId: int = Query(None, description="Endpoint ID to install app on, if not set install on the local endpoint"),
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    service = SetupWizardService()
    service.require_enabled()
    return service.install_app(payload.model_dump(), session_token=session_token, endpoint_id=endpointId)


@router.get(
    "/setup-wizard/install/{tracking_id}",
    summary="Get marketplace app installation status",
    responses={200: {"model": SetupWizardInstallStatusResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_marketplace_app_install_status(tracking_id: str):
    service = SetupWizardService()
    service.require_enabled()
    return service.get_install_status(tracking_id)


@router.post(
    "/setup-wizard/complete",
    summary="Mark setup wizard complete",
    responses={200: {"model": SetupWizardCompleteResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def complete_setup_wizard(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    service = SetupWizardService()
    service.require_enabled()
    return service.complete(session_token=session_token)