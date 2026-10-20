from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import click

from src.core.exception import CustomException


UPGRADE_DISPATCH_URL = "http://127.0.0.1:8080/api/settings/internal/upgrade/auto-prepare"
UPGRADE_PREPARE_URL = "http://127.0.0.1:8080/api/settings/internal/upgrade/prepare"
UPGRADE_DISPATCH_SECRET_HEADER = "x-websoft9-upgrade-dispatch-secret"


def dispatch_upgrade_preparation(
    *, automatic: bool = False, opener: Callable[..., Any] | None = None
) -> dict[str, Any]:
    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
    secret_path = Path(os.getenv(
        "WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE",
        f"{data_root}/config/internal-gateway-auth/trust_key",
    ))
    try:
        secret = secret_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise click.ClickException(f"Unable to read the upgrade dispatcher credential: {exc}") from exc
    if not secret:
        raise click.ClickException("The upgrade dispatcher credential is empty")

    request = Request(
        UPGRADE_DISPATCH_URL if automatic else UPGRADE_PREPARE_URL,
        data=b"",
        headers={UPGRADE_DISPATCH_SECRET_HEADER: secret},
        method="POST",
    )
    try:
        with (opener or urlopen)(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise CustomException(exc.code, "Upgrade Dispatch Failed", f"AppHub rejected upgrade preparation (HTTP {exc.code})") from exc
    except (OSError, URLError, ValueError) as exc:
        raise CustomException(503, "Upgrade Dispatch Unavailable", f"Unable to dispatch the upgrade download to AppHub: {exc}") from exc
    if not isinstance(payload, dict):
        raise click.ClickException("AppHub returned an invalid upgrade dispatcher response")
    if not automatic and (not payload.get("run_id") or not payload.get("state")):
        raise click.ClickException("AppHub did not acknowledge an upgrade preparation run")
    return payload
