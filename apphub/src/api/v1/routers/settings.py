import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Cookie, Path, Query, Request, Response
from src.schemas.appSettings import AppSettings, PlatformGatewayBatchUpdateRequest, GenerateSelfSignedCertRequest, ApplyLetsEncryptCertRequest, UploadCertRequest
from src.schemas.errorResponse import ErrorResponse
from src.schemas.productRuntimeState import ProductEditionStateResponse
from src.schemas.settingsSummary import SettingsSummaryResponse

from src.services.settings_manager import SettingsManager
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME, ProductAuthService
from src.services.product_runtime_state import read_product_runtime_state, read_release_version, read_release_channel
from src.services.release_checker import ARTIFACT_BASE_URL, ReleaseVersionChecker
from src.services.upgrade_manager import UpgradeManager, maybe_start_auto_download

router = APIRouter()


def _is_release_candidate(version: Optional[str]) -> bool:
    return "-rc" in str(version or "").lower()


def _parse_version(version: Optional[str]) -> Optional[tuple[int, int, int]]:
    match = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?", str(version or "").strip())
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _is_newer_stable_version(latest_version: Optional[str], current_version: Optional[str]) -> bool:
    latest = _parse_version(latest_version)
    current = _parse_version(current_version)
    return bool(latest and current and not _is_release_candidate(latest_version) and latest > current)


def _upgrade_status_payload(*, refresh_latest: bool = False) -> dict:
    """Latest version comes from the cached daily check; only a missing or stale entry hits
    the artifact server."""
    current_version = read_release_version() or ""
    channel = read_release_channel()
    latest_version = ReleaseVersionChecker().ensure_latest_version(
        channel=channel,
        force=refresh_latest,
        background=refresh_latest,
    )
    if refresh_latest:
        # An explicit check that finds a newer release also stages it, so the operator only has
        # to confirm the install. `upgrade.auto_download = false` turns this off.
        maybe_start_auto_download(latest_version=latest_version, current_version=current_version)
    # Read the state after the check: it may just have switched to `downloading`.
    status = UpgradeManager().status()
    artifact_url = f"{ARTIFACT_BASE_URL}/{channel}/install.sh"

    return {
        **status,
        "current_version": current_version,
        "channel": channel,
        "latest_version": latest_version or current_version,
        "upgrade_available": _is_newer_stable_version(latest_version, current_version),
        "install_command": f"wget -O install.sh {artifact_url} && sudo bash install.sh",
        "artifact_url": artifact_url,
        "doc_url": "https://github.com/Websoft9/websoft9/blob/main/install/upgrade-guide.md",
    }


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
    settings = SettingsManager().read_all()
    settings.api_key.key = "********"
    return settings

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
def apply_platform_gateway_settings(
    payload: PlatformGatewayBatchUpdateRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
):
    manager = SettingsManager()
    was_https_enabled = manager._is_platform_https_enabled()
    will_enable_https = manager._parse_bool(payload.https_enabled)
    request_is_https = (request.headers.get("x-forwarded-proto") or request.url.scheme) == "https"

    result = manager.write_platform_gateway_settings(
        bound_domain=payload.bound_domain,
        https_enabled=payload.https_enabled,
        force_https=payload.force_https,
        ssl_cert=payload.ssl_cert,
        ssl_key=payload.ssl_key,
        restart_gateway=False,
    )

    if was_https_enabled and not will_enable_https and request_is_https:
        response.delete_cookie(
            key=PRODUCT_AUTH_COOKIE_NAME,
            path="/",
            samesite="lax",
            secure=True,
        )

    background_tasks.add_task(manager._restart_platform_gateway)
    return result


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
    "/settings/upgrade/status",
    summary="Get upgrade status",
    description="Return current version, latest available version, and the recommended host upgrade command",
    responses={
        200: {"model": dict},
        500: {"model": ErrorResponse},
    },
)
def get_upgrade_status():
    return _upgrade_status_payload()


@router.post(
    "/settings/upgrade/check",
    status_code=200,
    summary="Re-check the artifact channel for a newer platform release",
    description="Force a fresh release check and refresh the cached latest version",
    responses={
        200: {"model": dict},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def check_upgrade(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    ProductAuthService()._require_authenticated_operator(session_token)
    return _upgrade_status_payload(refresh_latest=True)


@router.post(
    "/settings/upgrade/prepare",
    status_code=202,
    summary="Download the next upgrade in the background",
    responses={
        202: {"model": dict},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
def prepare_upgrade(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    ProductAuthService()._require_authenticated_operator(session_token)
    return UpgradeManager().start_prepare()


@router.post(
    "/settings/upgrade/apply",
    status_code=202,
    summary="Start a prepared in-console upgrade",
    responses={
        202: {"model": dict},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
def apply_upgrade(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    ProductAuthService()._require_authenticated_operator(session_token)
    return UpgradeManager().apply()


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