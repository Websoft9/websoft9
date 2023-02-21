import logging

import api.v1.api as api_router_v1
import uvicorn
from fastapi import FastAPI

logging_format = '[%(asctime)s][%(levelname)s] %(message)s'
logging.basicConfig(format=logging_format, level=logging.DEBUG)
logging.getLogger().setLevel(level=logging.DEBUG)
logging.info("Starting server")


def get_app():
    app = FastAPI()
    app.include_router(api_router_v1.get_api(), prefix="/api/v1")
    return app


if __name__ == "__main__":
    uvicorn.run("main:get_app", host='0.0.0.0', port=5000, reload=True)
