"""
System Initialization Status API
Returns status of service initialization
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json
from pathlib import Path

router = APIRouter()

STATUS_FILE = Path("/websoft9/apphub/logs/init-status.json")

@router.get("/init/status",
    summary="Get initialization status",
    description="Returns the initialization status of all services in the cockpit container",
    tags=["system"]
)
async def get_init_status():
    """
    Get service initialization status
    
    Returns JSON with:
    - initialized_at: Timestamp of initialization
    - services: Dict of service statuses (pending/initializing/success/failed)
    """
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                status_data = json.load(f)
            return JSONResponse(content=status_data, status_code=200)
        else:
            # Status file not yet created (container just started)
            return JSONResponse(
                content={
                    "initialized_at": None,
                    "services": {
                        "cockpit": {"status": "pending", "message": "Initialization in progress"},
                        "apphub": {"status": "pending", "message": "Initialization in progress"},
                        "gitea": {"status": "pending", "message": "Initialization in progress"},
                        "portainer": {"status": "pending", "message": "Initialization in progress"}
                    },
                    "note": "Container initialization in progress, status file not yet created"
                },
                status_code=200
            )
    except Exception as e:
        return JSONResponse(
            content={
                "error": "Failed to read initialization status",
                "details": str(e)
            },
            status_code=500
        )
