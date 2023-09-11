from fastapi import FastAPI
from src.api.v1.routers import app as api_app
from src.api.v1.routers import settings as api_settings

app = FastAPI(
        title="FastAPI Template",
        description="FastAPI Template 123",
        version="0.0.1"
    )

app.include_router(api_app.router,tags=["apps"])
app.include_router(api_settings.router,tags=["settings"])
