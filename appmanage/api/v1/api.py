from fastapi import APIRouter

from api.v1.routers import health,apps


def get_api():
    api_router = APIRouter()
    api_router.include_router(health.router)
    api_router.include_router(apps.router)
    return api_router
