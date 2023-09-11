from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from pydantic import BaseModel

from src.schemas.appInstall import appInstallPayload

router = APIRouter()

@router.get("/apps/")
def get_apps():
    return {"apps": "apps"}

@router.post("/apps/install",summary="Install App",description="Install an app on an endpoint",responses={400: {"description": "Invalid EndpointId"}, 500: {"description": "Internal Server Error"}})
def apps_install(app_install_payload: appInstallPayload, endpointId: str = Query(..., description="Endpoint ID to install app on")):
    try:
        if endpointId < 0:
            raise HTTPException(status_code=400, detail="Invalid EndpointId")
        app_name = app_install_payload.app_name
        return app_name
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")