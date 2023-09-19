from fastapi import APIRouter, Query
from typing import List, Optional

router = APIRouter()

@router.get("/proxys".format(),summary="Get proxys",description="Get proxys")
def get_proxys():
    return {"proxys": "proxys"}

@router.put("/proxys")
def update_settings():
    return {"proxys": "proxys"}