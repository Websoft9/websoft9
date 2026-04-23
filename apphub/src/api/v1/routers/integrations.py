from typing import Literal

from fastapi import APIRouter, Response

from src.services.integration_session_bridge import IntegrationSessionBridge

router = APIRouter()


@router.post("/integrations/{integration_key}/session")
def bootstrap_integration_session(
    response: Response,
    integration_key: Literal["gitea", "portainer", "npm"],
):
    cookies = IntegrationSessionBridge().bootstrap(integration_key)

    for cookie in cookies:
        response.set_cookie(
            key=str(cookie["name"]),
            value=str(cookie["value"]),
            path=str(cookie.get("path") or "/"),
            httponly=bool(cookie.get("httponly", False)),
            samesite="lax",
        )

    return {"status": "ok", "integration": integration_key}