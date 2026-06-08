import logging, os, sys
from uuid import uuid4
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.requests import HTTPConnection
from src.api.v1.routers import app as api_app
from src.api.v1.routers import auth as api_auth
from src.api.v1.routers import files as api_files
from src.api.v1.routers import host_access as api_host_access
from src.api.v1.routers import integrations as api_integrations
from src.api.v1.routers import logs as api_logs
from src.api.v1.routers import overview as api_overview
from src.api.v1.routers import services as api_services
from src.api.v1.routers import settings as api_settings
from src.api.v1.routers import proxy as api_proxy
from src.api.v1.routers import backup as api_backup
from src.api.v1.routers import compose_app as api_compose_app
from src.api.v1.routers import appstore_sync as api_appstore_sync
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.api_key_auth import should_skip_api_key_auth
from src.core.logger import clear_logging_context, logger, set_request_id
from src.core.request_auth import has_valid_internal_gateway_auth
from src.schemas.errorResponse import ErrorResponse

uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.setLevel(logging.INFO)

API_KEY_NAME = "x-api-key"
INTERNAL_GATEWAY_TRUST_KEY_FILE = os.getenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", "/etc/custom/internal-gateway-auth/trust_key")

async def verify_key(connection: HTTPConnection):
    # logger.access("request.url.path: "+request.url.path)
    """
    Verify API Key
    """
    if should_skip_api_key_auth(connection.url.path):
        return None

    api_key_header = connection.headers.get(API_KEY_NAME)

    internal_gateway_secret = None
    if os.path.exists(INTERNAL_GATEWAY_TRUST_KEY_FILE):
        with open(INTERNAL_GATEWAY_TRUST_KEY_FILE, "r", encoding="utf-8") as handle:
            internal_gateway_secret = handle.read().strip() or None

    if has_valid_internal_gateway_auth(connection.headers, internal_gateway_secret):
        return None

    # validate api key is provided
    if api_key_header is None:
        raise CustomException(
            status_code=400, 
            message="Invalid Request",
            details="No API Key provided"
        )

    try:
        API_KEY = ConfigManager().get_value("api_key","key")
    except Exception:
        API_KEY = None

    # validate api key is set
    if API_KEY is None:
        raise CustomException(
            status_code=500, 
            message="Invalid API Key",
            details="API Key is not set"
        )
    # validate api key is correct
    if api_key_header != API_KEY:
        logger.error(f"Invalid API Key: {api_key_header}")
        raise CustomException(
            status_code=400, 
            message="Invalid Request",
            details="Invalid API Key"
        )
    return api_key_header
    
app = FastAPI(
        title="AppHub API",
        description="This documentation describes the AppHub API.",
        version="0.0.1",
        docs_url=None,
        root_path="/api",
        servers=[{"url": "/api"}],
        dependencies=[Depends(verify_key)],
    )


@app.middleware("http")
async def request_logging_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    set_request_id(request_id)
    try:
        response = await call_next(request)
        response.headers.setdefault("x-request-id", request_id)
        return response
    finally:
        clear_logging_context()

@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="AppHub API",
    )

# remove 422 responses
def remove_422_responses():
    original_openapi = app.openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = original_openapi()
        for path, path_item in openapi_schema["paths"].items():
            for method, operation in path_item.items():
                operation["responses"].pop("422", None)
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

#custom error handler
@app.exception_handler(CustomException)
async def custom_exception_handler(request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(message=exc.message, details=exc.details).model_dump(),
    )

# 422 error handler:set 422 response to 400
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    #errors = {err['loc'][1]: err['msg'] for err in exc.errors()}
    errors = ", ".join(f"{err['loc'][1]}: {err['msg']}" for err in exc.errors())
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(message="Request Validation Error", details=errors).model_dump(),
    )

app.include_router(api_app.router,tags=["apps"])
app.include_router(api_auth.router,tags=["auth"])
app.include_router(api_files.router,tags=["files"])
app.include_router(api_host_access.router,tags=["host-access"])
app.include_router(api_integrations.router,tags=["integrations"])
app.include_router(api_logs.router,tags=["logs"])
app.include_router(api_overview.router,tags=["overview"])
app.include_router(api_services.router,tags=["services"])
app.include_router(api_proxy.router,tags=["proxys"])
app.include_router(api_backup.router,tags=["backup"])
app.include_router(api_settings.router,tags=["settings"])
app.include_router(api_compose_app.router,tags=["compose-apps"])
app.include_router(api_appstore_sync.router,tags=["appstore-sync"])

remove_422_responses()