from api.utils.common_log import myLogger

import api.v1.api as api_router_v1
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

myLogger.info_logger("Starting server")

def get_app():
    app = FastAPI()
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(api_router_v1.get_api(), prefix="/api/v1")
    return app


if __name__ == "__main__":
    uvicorn.run("main:get_app", host='0.0.0.0', port=5000, reload=True)
