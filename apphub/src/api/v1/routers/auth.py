from typing import Optional

from fastapi import APIRouter, Cookie, Header, Request, Response

from src.schemas.errorResponse import ErrorResponse
from src.schemas.productAuth import (
    ProductAuthCreateUserRequest,
    ProductAuthFavoriteRequest,
    ProductAuthFavoritesResponse,
    ProductAuthInitializeRequest,
    ProductAuthLoginRequest,
    ProductAuthOperator,
    ProductAuthResetPasswordRequest,
    ProductAuthStatusResponse,
    ProductAuthUpdateUserRequest,
    ProductAuthUsersResponse,
)
from src.services.product_auth import PRODUCT_AUTH_COOKIE_NAME, ProductAuthService

router = APIRouter()


def _set_session_cookie(request: Request, response: Response, session_token: str) -> None:
    response.set_cookie(
        key=PRODUCT_AUTH_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30,
        secure=(request.headers.get("x-forwarded-proto") or request.url.scheme) == "https",
    )


@router.get(
    "/auth/status",
    summary="Get product auth status",
    description="Get product-side authentication capability, initialization state, and current session status",
    responses={200: {"model": ProductAuthStatusResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_product_auth_status(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return ProductAuthService().get_status(session_token=session_token)


@router.get(
    "/auth/session",
    summary="Get current product auth session",
    description="Get the current product-side session and authenticated operator when present",
    responses={200: {"model": ProductAuthStatusResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_product_auth_session(
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
):
    return ProductAuthService().get_status(session_token=session_token)


@router.get(
    "/auth/users",
    summary="List product-side operators",
    description="List active and disabled product-side operators for the user-management module",
    responses={200: {"model": ProductAuthUsersResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_product_auth_users(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return {"users": ProductAuthService().list_operators(session_token=session_token)}


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
        locale=payload.locale,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )
    _set_session_cookie(request, response, session_token)
    return status_payload


@router.post(
    "/auth/users",
    summary="Create product-side operator",
    description="Create an additional product-side operator account",
    responses={200: {"model": ProductAuthOperator}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_product_auth_user(
    payload: ProductAuthCreateUserRequest,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return ProductAuthService().create_operator(
        session_token=session_token,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        locale=payload.locale,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )


@router.put(
    "/auth/users/{operator_id}",
    summary="Update product-side user",
    description="Update a product-side user profile",
    responses={200: {"model": ProductAuthOperator}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def update_product_auth_user(
    operator_id: str,
    payload: ProductAuthUpdateUserRequest,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return ProductAuthService().update_operator(
        session_token=session_token,
        target_operator_id=operator_id,
        display_name=payload.display_name,
        locale=payload.locale,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )


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
    _set_session_cookie(request, response, session_token)
    return status_payload


@router.post(
    "/auth/users/{operator_id}/disable",
    summary="Disable product-side operator",
    description="Disable a product-side operator and invalidate their sessions",
    responses={200: {"model": ProductAuthOperator}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def disable_product_auth_user(
    operator_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return ProductAuthService().disable_operator(
        session_token=session_token,
        target_operator_id=operator_id,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )


@router.post(
    "/auth/users/{operator_id}/enable",
    summary="Enable product-side operator",
    description="Enable a product-side operator so the account can sign in again",
    responses={200: {"model": ProductAuthOperator}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def enable_product_auth_user(
    operator_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return ProductAuthService().enable_operator(
        session_token=session_token,
        target_operator_id=operator_id,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )


@router.post(
    "/auth/users/{operator_id}/reset-password",
    summary="Reset product-side operator password",
    description="Reset a product-side operator password and invalidate active sessions",
    responses={200: {"model": ProductAuthOperator}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def reset_product_auth_user_password(
    operator_id: str,
    payload: ProductAuthResetPasswordRequest,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return ProductAuthService().reset_operator_password(
        session_token=session_token,
        target_operator_id=operator_id,
        password=payload.password,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )


@router.delete(
    "/auth/users/{operator_id}",
    summary="Delete product-side operator",
    description="Soft-delete a product-side operator and invalidate active sessions",
    responses={200: {"model": ProductAuthOperator}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def delete_product_auth_user(
    operator_id: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return ProductAuthService().delete_operator(
        session_token=session_token,
        target_operator_id=operator_id,
        client_host=request.client.host if request.client else None,
        user_agent=user_agent,
    )


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


@router.get(
    "/auth/favorites",
    summary="List current user favorites",
    description="List app-store favorites for the current authenticated product-side user",
    responses={200: {"model": ProductAuthFavoritesResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def list_product_auth_favorites(session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME)):
    return {"favorites": ProductAuthService().list_favorites(session_token=session_token)}


@router.post(
    "/auth/favorites",
    summary="Add app-store favorite",
    description="Store an app-store favorite for the current authenticated product-side user",
    responses={200: {"model": ProductAuthFavoritesResponse}, 400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_product_auth_favorite(
    payload: ProductAuthFavoriteRequest,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return {
        "favorites": ProductAuthService().add_favorite(
            session_token=session_token,
            app_key=payload.app_key,
            client_host=request.client.host if request.client else None,
            user_agent=user_agent,
        )
    }


@router.delete(
    "/auth/favorites/{app_key}",
    summary="Remove app-store favorite",
    description="Remove an app-store favorite for the current authenticated product-side user",
    responses={200: {"model": ProductAuthFavoritesResponse}, 401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def delete_product_auth_favorite(
    app_key: str,
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=PRODUCT_AUTH_COOKIE_NAME),
    user_agent: Optional[str] = Header(default=None),
):
    return {
        "favorites": ProductAuthService().remove_favorite(
            session_token=session_token,
            app_key=app_key,
            client_host=request.client.host if request.client else None,
            user_agent=user_agent,
        )
    }