import argparse
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)

import api.v1.api as api_router_v1

from api.utils.common_log import myLogger
from api.utils import shell_execute
from api.settings.settings import settings


myLogger.info_logger("Start server...")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url="/")


def get_app():
    settings.init_config_from_file()
    origins = [
        "http://localhost",
        "http://localhost:9090",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(api_router_v1.get_api())
    return app

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
    )

@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc/redoc.standalone.js",
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='websoft9')
    parser.add_argument("--port", type=int, dest='port', default=5000, metavar="port")
    parser.add_argument("--config", type=str, dest="config_file", required=True)
    args = parser.parse_args()
    settings.init_config_from_file(config_file=args.config_file)
    uvicorn.run("main:get_app", host='0.0.0.0', port=args.port, reload=True)