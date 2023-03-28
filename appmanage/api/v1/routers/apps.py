from typing import Optional, List

from fastapi import APIRouter, status, Depends
from pydantic import BaseModel
from starlette.responses import JSONResponse
import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.model.app import App
from api.service import manage
from api.utils import shell_execute
from api.utils.common_log import myLogger

router = APIRouter()

@router.api_route("/details", methods=["GET", "POST"])
def app_detail(app_id: Optional[str] = None):
    myLogger.info_logger("Receive request: /api/v1/apps/details")
    list = manage.get_app_detail(app_id)
    return JSONResponse(list)

@router.api_route("", methods=["GET", "POST"])
def list_my_apps():
    myLogger.info_logger("Receive request: /api/v1/apps")
    list = manage.get_my_app()
    return JSONResponse(content=list)

@router.api_route("/install", methods=["GET", "POST"])
def install_app(app_name: Optional[str] = None, customer_app_name: Optional[str] = None, app_version: Optional[str] = None):
    myLogger.info_logger("Receive request: /api/v1/apps/install")
    ret = manage.install_app(app_name, customer_app_name, app_version)
    return JSONResponse(content=ret)

@router.api_route("/process", methods=["GET", "POST"])
def install_app_process(app_id: Optional[str] = None):
    myLogger.info_logger("Receive request: /api/v1/apps/process")
    ret = manage.install_app_process(app_id)
    return JSONResponse(content=ret)

@router.api_route("/start", methods=["GET", "POST"])
def start_app(app_id: Optional[str] = None):
    myLogger.info_logger("Receive request: /api/v1/apps/start")
    ret = manage.start_app(app_id)
    return JSONResponse(content=ret)

@router.api_route("/stop", methods=["GET", "POST"])
def stop_app(app_id: Optional[str] = None):
    myLogger.info_logger("Receive request: /api/v1/apps/stop")
    ret = manage.stop_app(app_id)
    return JSONResponse(content=ret)

@router.api_route("/restart", methods=["GET", "POST"])
def restart_app(app_id: Optional[str] = None):
    myLogger.info_logger("Receive request: /api/v1/apps/restart")
    ret = manage.restart_app(app_id)
    return JSONResponse(content=ret)

@router.api_route("/uninstall", methods=["GET", "POST"])
def uninstall_app(app_id: Optional[str] = None):
    myLogger.info_logger("Receive request: /api/v1/apps/uninstall")
    ret = manage.uninstall_app(app_id)
    return JSONResponse(content=ret)
