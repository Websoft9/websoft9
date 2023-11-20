import logging, sys
from fastapi import FastAPI, Request,Security,Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from src.api.v1.routers import app as api_app
from src.api.v1.routers import settings as api_settings
from src.api.v1.routers import proxy as api_proxy
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger
from src.schemas.errorResponse import ErrorResponse
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader

# set uvicorn logger to stdout
uvicorn_logger = logging.getLogger("uvicorn")
stdout_handler = logging.StreamHandler(sys.stdout)
uvicorn_logger.addHandler(stdout_handler)
uvicorn_logger.setLevel(logging.INFO)

API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_key(request: Request, api_key_header: str = Security(api_key_header)):
    """
    Verify API Key
    """
    # skip docs
    if request.url.path == "/api/docs":
        return None 

    # validate api key is provided
    if api_key_header is None:
        raise CustomException(
            status_code=400, 
            message="Invalid Request",
            details="No API Key provided"
        )
    # get api key from config
    API_KEY = ConfigManager().get_value("api_key","key")
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

app.mount("/static", StaticFiles(directory="swagger-ui"), name="static")

@app.get("/docs", response_class=HTMLResponse,include_in_schema=False,)
async def custom_swagger_ui_html():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AppHub API</title>
        <link rel="stylesheet" type="text/css" href="/api/static/swagger-ui.css">
        <script src="/api/static/swagger-ui-bundle.js"></script>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script>
        const ui = SwaggerUIBundle({
            url: "/api/openapi.json",
            dom_id: '#swagger-ui',
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
            layout: "BaseLayout"
        })
        </script>
    </body>
    </html>
    """

# remove 422 responses
async def remove_422_responses():
    openapi_schema = app.openapi()
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            operation["responses"].pop("422", None)
    app.openapi_schema = openapi_schema

app.add_event_handler("startup", remove_422_responses)

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
app.include_router(api_proxy.router,tags=["proxys"])
app.include_router(api_settings.router,tags=["settings"])