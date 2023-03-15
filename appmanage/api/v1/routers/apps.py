from typing import Optional, List

from fastapi import APIRouter, status, Depends
from pydantic import BaseModel
from starlette.responses import JSONResponse
import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.model.app import App
from api.service import manage
from api.utils import shell_execute

router = APIRouter()

@router.get("")
def list_my_apps():
    list = manage.get_my_app()
    return JSONResponse(content=list)

@router.get("/install")
def install_app(app_name: Optional[str] = None, customer_app_name: Optional[str] = None, app_version: Optional[str] = None, app_force: Optional[bool] = False):
    ret = manage.install_app(app_name, customer_app_name, app_version, app_force)
    return JSONResponse(content=ret)

@router.get("/process")
def install_app_process(app_name: Optional[str] = None):
    ret = manage.install_app_process(app_name)
    return JSONResponse(content=ret)

@router.get("/start")
def start_app(app_name: Optional[str] = None):
    ret = manage.start_app(app_name)
    return JSONResponse(content=ret)

@router.get("/stop")
def stop_app(app_name: Optional[str] = None):
    ret = manage.stop_app(app_name)
    return JSONResponse(content=ret)

@router.get("/restart")
def restart_app(app_name: Optional[str] = None):
    ret = manage.restart(app_name)
    return JSONResponse(content=ret)

@router.get("/uninstall")
def uninstall_app(app_id: Optional[str] = None, delete_flag: Optional[bool] = True):
    ret = manage.uninstall_app(app_id, delete_flag)
    return JSONResponse(content=ret)
