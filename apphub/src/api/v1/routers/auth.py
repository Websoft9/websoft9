from typing import Optional

from fastapi import APIRouter, Cookie, Header, Request, Response

from src.schemas.errorResponse import ErrorResponse
from src.schemas.productAuth import (
    ProductAuthInitializeRequest,
    ProductAuthLoginRequest,
    ProductAuthStatusResponse,
)
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME, ProductAuthService

router = APIRouter()


@router.get(
    "/auth/status",
    summary="Get product auth status",
    description="Get product-side authentication capability, initialization state, and current session status",
    responses={200: {"model": ProductAuthStatusResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_product_auth_status(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return ProductAuthService().get_status(session_token=session_token)


@router.get(
    "/auth/session",
    summary="Get current product auth session",
    description="Get the current product-side session and authenticated operator when present",
    responses={200: {"model": ProductAuthStatusResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_product_auth_session(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return ProductAuthService().get_status(session_token=session_token)


@router.post(
    "/auth/initialize",
    summary="Initialize first operator",
    description="Create the first product-side operator account and open a product-owned session",
    responses={200: {"model": ProductAuthStatusResponse}, 400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def initialize_first_operator(
    payload: ProductAuthInitializeRequest,
    request: Request,
    response: Response,
    user_agent: Optional[str] = Header(default=None),
):
    status_payload, session_token = ProductAuthService().initialize_first_operator(
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )
    response.set_cookie(
        key=PRODUCT_AUTH_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30,
        secure=(request.headers.get("x-forwarded-proto") or request.url.scheme) == "https",
    )
    return status_payload


@router.post(
    "/auth/login",
    summary="Operator login",
    description="Authenticate an existing product-side operator and create a product-owned session",
    responses={200: {"model": ProductAuthStatusResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def login_operator(
    payload: ProductAuthLoginRequest,
    request: Request,
    response: Response,
    user_agent: Optional[str] = Header(default=None),
):
    status_payload, session_token = ProductAuthService().login(
        username=payload.username,
        password=payload.password,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )
    response.set_cookie(
        key=PRODUCT_AUTH_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30,
        secure=(request.headers.get("x-forwarded-proto") or request.url.scheme) == "https",
    )
    return status_payload


@router.post(
    "/auth/logout",
    summary="Operator logout",
    description="Invalidate the current product-side session",
    responses={200: {"model": ProductAuthStatusResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def logout_operator(
    request: Request,
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    status_payload = ProductAuthService().logout(
        session_token=session_token,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )
    response.delete_cookie(key=PRODUCT_AUTH_COOKIE_NAME, path="/", samesite="lax")
    return status_payload