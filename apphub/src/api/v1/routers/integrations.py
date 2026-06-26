from typing import Literal, Optional

from fastapi import APIRouter, Header, Response

from src.services.integration_session_bridge import IntegrationSessionBridge

router = APIRouter()


def _set_session_cookies(response: Response, cookies: list[dict[str, object]]) -> None:
    for cookie in cookies:
        response.set_cookie(
            key=str(cookie["name"]),
            value=str(cookie["value"]),
            path=str(cookie.get("path") or "/"),
            httponly=bool(cookie.get("httponly", False)),
            samesite="lax",
            max_age=int(cookie["max_age"]) if cookie.get("max_age") is not None else None,
        )


@router.post("/integrations/session")
def bootstrap_all_integration_sessions(
    response: Response,
    x_websoft9_locale: Optional[str] = Header(default=None),
):
    payload = IntegrationSessionBridge().bootstrap_all(locale=x_websoft9_locale)
    _set_session_cookies(response, payload.pop("cookies"))
    return payload


@router.post("/integrations/{integration_key}/session")
def bootstrap_integration_session(
    response: Response,
    integration_key: Literal["gitea", "portainer", "npm"],
    x_websoft9_locale: Optional[str] = Header(default=None),
):
    cookies = IntegrationSessionBridge().bootstrap(integration_key, locale=x_websoft9_locale)
    _set_session_cookies(response, cookies)

    return {"status": "ok", "integration": integration_key}