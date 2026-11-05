from dataclasses import dataclass
from typing import Optional, Tuple

from src.core.exception import CustomException
from src.schemas.appInstall import Edition, appInstall
from src.schemas.appRuntimeInstall import (
    RUNTIME_TEMPLATES,
    RUNTIME_VERSIONS,
    RuntimeInstallRequest,
    RuntimeInstallValidationPayload,
)

DEFAULT_NETWORK_NAME = "websoft9"


@dataclass(frozen=True)
class RuntimeProfile:
    """Static description of how one runtime family is installed through a template application."""

    key: str
    label: str
    template_app_name: str
    default_app_port: Optional[int]
    template_label: Optional[str] = None
    url_replace_default: bool = False


# The template each runtime family is deployed with. Templates live in the application catalog, so
# this table only records which of them a runtime may target and what that costs by default.
RUNTIME_PROFILES = {
    "php": RuntimeProfile(
        key="php",
        label="PHP Runtime",
        template_app_name="php",
        default_app_port=80,
        url_replace_default=True,
    ),
    "nodejs": RuntimeProfile(
        key="nodejs",
        label="Node.js Runtime",
        template_app_name="nodejs",
        default_app_port=None,
    ),
    "java": RuntimeProfile(
        key="java",
        label="Java Runtime",
        template_app_name="tomcat",
        default_app_port=8080,
        template_label="Tomcat",
    ),
    "python": RuntimeProfile(
        key="python",
        label="Python Runtime",
        template_app_name="python",
        default_app_port=8000,
    ),
}


def _resolve_template(payload: RuntimeInstallRequest, profile: RuntimeProfile) -> str:
    template = payload.template_app_name or profile.template_app_name
    if template not in RUNTIME_TEMPLATES[payload.runtime_key]:
        raise CustomException(
            400, "Invalid Request", f"Unsupported template '{template}' for runtime '{payload.runtime_key}'."
        )
    return template


def _resolve_app_port(payload: RuntimeInstallRequest, profile: RuntimeProfile) -> int:
    app_port = payload.app_port if payload.app_port is not None else profile.default_app_port
    if app_port is None:
        raise CustomException(400, "Invalid Request", "The selected runtime requires an internal application port.")
    return app_port


def _resolve_url(payload: RuntimeInstallRequest) -> str:
    return (payload.domain or payload.runtime_url or payload.fallback_host).strip()


def _resolve_url_replace(payload: RuntimeInstallRequest, profile: RuntimeProfile) -> bool:
    if payload.url_replace is None:
        return profile.url_replace_default
    return payload.url_replace


def _build_settings(
    host_port: int,
    app_port: int,
    url: str,
    network_name: str,
    url_replace: bool,
    url_replace_requested: bool,
) -> dict:
    settings = {
        "W9_HTTP_PORT_SET": str(host_port),
        "W9_HTTP_PORT": str(app_port),
        "W9_URL": url,
        "W9_NETWORK": network_name,
    }
    # A runtime that rewrites URLs by default always states it; one that does not only states the
    # flag when the operator asked for an explicit value, so the template default stays untouched.
    if url_replace or url_replace_requested:
        settings["W9_URL_REPLACE"] = "true" if url_replace else "false"
    return settings


def build_runtime_installation(payload: RuntimeInstallRequest) -> Tuple[appInstall, RuntimeInstallValidationPayload]:
    """Normalize a runtime-source request into the regular application install contract."""
    profile = RUNTIME_PROFILES[payload.runtime_key]

    if payload.version not in RUNTIME_VERSIONS[payload.runtime_key]:
        raise CustomException(
            400,
            "Invalid Request",
            f"Unsupported version '{payload.version}' for runtime '{payload.runtime_key}'.",
        )

    template_app_name = _resolve_template(payload, profile)
    app_port = _resolve_app_port(payload, profile)
    url = _resolve_url(payload)
    network_name = (payload.network_name or DEFAULT_NETWORK_NAME).strip()
    proxy_enabled = bool(payload.domain)
    domain_names = [payload.domain] if payload.domain else [payload.fallback_host]
    url_replace = _resolve_url_replace(payload, profile)
    runtime_label = f"{profile.label} ({profile.template_label})" if profile.template_label else profile.label

    install_payload = appInstall(
        app_name=template_app_name,
        edition=Edition(dist="community", version=payload.version),
        app_id=payload.app_id,
        proxy_enabled=proxy_enabled,
        domain_names=domain_names,
        settings=_build_settings(
            host_port=payload.host_port,
            app_port=app_port,
            url=url,
            network_name=network_name,
            url_replace=url_replace,
            url_replace_requested=payload.url_replace is not None,
        ),
        profile=None,
    )

    validation_payload = RuntimeInstallValidationPayload(
        template_app_name=template_app_name,
        runtime_label=runtime_label,
        proxy_enabled=proxy_enabled,
        domain_names=domain_names,
        app_port=app_port,
        runtime_url=url,
        network_name=network_name,
        url_replace=url_replace,
    )

    return install_payload, validation_payload
