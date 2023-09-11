from fastapi import APIRouter, Query
from typing import List, Optional

router = APIRouter()

@router.get("/settings",summary="Get settings",description="Get settings")
def get_settings():
    return {"settings": "settings"}

@router.put("/settings")
def update_settings():
    return {"settings": "settings"}