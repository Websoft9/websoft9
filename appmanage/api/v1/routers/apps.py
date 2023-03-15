from typing import Optional, List

from fastapi import APIRouter, status, Depends
from pydantic import BaseModel
from starlette.responses import JSONResponse
import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.model.app import App
from api.service import manage
from api.utils import shell_execute

router = APIRouter()

@router.api_route("", methods=["GET", "POST"])
def list_my_apps():
    list = manage.get_my_app()
    return JSONResponse(content=list)

@router.api_route("/install", methods=["GET", "POST"])
def install_app(app_name: Optional[str] = None, customer_app_name: Optional[str] = None, app_version: Optional[str] = None, app_force: Optional[bool] = False):
    ret = manage.install_app(app_name, customer_app_name, app_version, app_force)
    return JSONResponse(content=ret)

@router.api_route("/process", methods=["GET", "POST"])
def install_app_process(app_id: Optional[str] = None):
    ret = manage.install_app_process(app_id)
    return JSONResponse(content=ret)

@router.api_route("/start", methods=["GET", "POST"])
def start_app(app_id: Optional[str] = None):
    ret = manage.start_app(app_id)
    return JSONResponse(content=ret)

@router.api_route("/stop", methods=["GET", "POST"])
def stop_app(app_id: Optional[str] = None):
    ret = manage.stop_app(app_id)
    return JSONResponse(content=ret)

@router.api_route("/restart", methods=["GET", "POST"])
def restart_app(app_id: Optional[str] = None):
    ret = manage.restart(app_id)
    return JSONResponse(content=ret)

@router.api_route("/uninstall", methods=["GET", "POST"])
def uninstall_app(app_id: Optional[str] = None, delete_flag: Optional[bool] = True):
    ret = manage.uninstall_app(app_id, delete_flag)
    return JSONResponse(content=ret)
