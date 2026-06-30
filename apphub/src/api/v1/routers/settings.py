from typing import Optional

from fastapi import APIRouter, Query, Path, Cookie
from src.schemas.appSettings import AppSettings, PlatformGatewayBatchUpdateRequest, GenerateSelfSignedCertRequest, ApplyLetsEncryptCertRequest, UploadCertRequest
from src.schemas.errorResponse import ErrorResponse
from src.schemas.productRuntimeState import ProductEditionStateResponse
from src.schemas.settingsSummary import SettingsSummaryResponse

from src.services.settings_manager import SettingsManager
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME, ProductAuthService
from src.services.product_runtime_state import read_product_runtime_state

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

@router.get("/settings/summary",
            summary="Get masked settings summary",
            description="Get native console settings summary with masked sensitive values",
            responses={
                200: {"model": SettingsSummaryResponse},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def get_settings_summary():
    return SettingsManager().read_summary()

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
    if section in {"gitea", "portainer", "nginx_proxy_manager"}:
        return {}
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


@router.put(
            "/settings/platform_gateway/apply",
            summary="Apply platform gateway settings",
            description="Update platform gateway domain, HTTPS, and certificate settings in one request",
            responses={
                200: {"model": AppSettings},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def apply_platform_gateway_settings(payload: PlatformGatewayBatchUpdateRequest):
    return SettingsManager().write_platform_gateway_settings(
        bound_domain=payload.bound_domain,
        https_enabled=payload.https_enabled,
        force_https=payload.force_https,
        ssl_cert=payload.ssl_cert,
        ssl_key=payload.ssl_key,
    )


@router.post(
    "/settings/platform_gateway/generate-self-signed-cert",
    summary="Generate a self-signed certificate for the platform gateway",
    responses={
        200: {"model": dict},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def generate_self_signed_cert(payload: GenerateSelfSignedCertRequest):
    return SettingsManager().generate_self_signed_cert(domain=payload.domain, validity_days=payload.validity_days)


@router.post(
    "/settings/platform_gateway/apply-letsencrypt-cert",
    summary="Apply for a Let's Encrypt certificate for the platform gateway",
    responses={
        200: {"model": dict},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def apply_letsencrypt_cert(payload: ApplyLetsEncryptCertRequest):
    return SettingsManager().apply_letsencrypt_cert(domain=payload.domain, email=payload.email)


@router.post(
    "/settings/platform_gateway/upload-cert",
    summary="Upload PEM certificate content to platform gateway paths",
    responses={
        200: {"model": dict},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def upload_cert(payload: UploadCertRequest):
    return SettingsManager().upload_cert(
        cert_pem=payload.cert_pem,
        key_pem=payload.key_pem,
        intermediate_pem=payload.intermediate_pem,
    )


@router.get(
    "/settings/internal/product-edition",
    summary="Get runtime product edition state",
    description="Get the current runtime product edition state for authenticated operator workflows",
    responses={
        200: {"model": ProductEditionStateResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def get_internal_product_edition_state(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    auth_service = ProductAuthService()
    auth_service._require_authenticated_operator(session_token)

    state = read_product_runtime_state()
    return ProductEditionStateResponse(
        version=state.version,
        edition_key=state.edition_key,
        edition_name=state.edition_name,
        max_apps=state.max_apps,
        state_source=state.state_source,
        updated_by=state.updated_by,
        updated_at=state.updated_at,
        note=state.note,
    )