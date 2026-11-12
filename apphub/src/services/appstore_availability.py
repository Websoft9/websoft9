from __future__ import annotations

import json
import os
from pathlib import Path

from src.core.exception import CustomException
from src.core.logger import logger

UNAVAILABLE_MESSAGE = "App Store Assets Unavailable"


def get_appstore_assets_state() -> dict:
    runtime_root = Path(os.getenv("WEBSOFT9_RUNTIME_STATE_DIR", "/run/websoft9"))
    path = Path(os.getenv("WEBSOFT9_APPSTORE_RUNTIME_STATE_FILE", str(runtime_root / "appstore-assets.json")))
    try:
        payload = json.loads(path.read_bytes())
        if (
            isinstance(payload, dict)
            and payload.get("status") in ("ready", "updating", "unavailable")
            and (
                payload["status"] != "ready"
                or (isinstance(payload.get("datasetVersion"), str) and payload["datasetVersion"].strip())
            )
        ):
            return payload
    except (OSError, ValueError) as exc:
        return {"status": "unavailable", "message": f"Cannot read Appstore availability record: {exc}"}
    return {"status": "unavailable", "message": "Appstore assets have not been verified in this container"}


def require_appstore_assets() -> None:
    state = get_appstore_assets_state()
    if state["status"] != "ready":
        detail = state.get("message") or "No complete verified Appstore dataset is available; synchronize before installing"
        logger.warning(f"Official Appstore unavailable: {detail}")
        raise CustomException(503, UNAVAILABLE_MESSAGE, str(detail))
