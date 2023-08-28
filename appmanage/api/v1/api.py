from fastapi import APIRouter

from .routers import health, apps


def get_api():
    api_router = APIRouter()
    api_router.include_router(health.router)
    api_router.include_router(apps.router)
    return api_router
