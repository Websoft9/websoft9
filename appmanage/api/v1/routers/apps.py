from typing import Optional, List

from fastapi import APIRouter, status, Depends, Query
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse
import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.model.app import App
from api.model.response import Response
from api.service import manage
from api.utils import shell_execute
from api.utils.common_log import myLogger

router = APIRouter()

rd = "code: 请求操作内部响应码\n\nmessage: 请求操作结果描述\n\ndata: 返回请求结果内容"


@router.api_route("/details", methods=["GET", "POST"], summary="获取指定APP的信息", response_description=rd,
                  response_model=Response)
def app_detail(app_id: Optional[str] = Query(default=None, description="应用ID")):
    myLogger.info_logger("Receive request: /api/v1/apps/details")
    list = manage.get_app_detail(app_id)
    return JSONResponse(list)


@router.api_route("", methods=["GET", "POST"], summary="获取所有APP的信息", response_description=rd, response_model=Response)
def list_my_apps():
    myLogger.info_logger("Receive request: /api/v1/apps")
    list = manage.get_my_app()
    return JSONResponse(content=list)


@router.api_route("/install", methods=["GET", "POST"], summary="安装APP", response_description=rd,
                  response_model=Response)
def install_app(app_name: Optional[str] = Query(default=None, description="应用名"),
                customer_app_name: Optional[str] = Query(default=None, description="应用自定义名字"),
                app_version: Optional[str] = Query(default=None, description="应用版本")):
    myLogger.info_logger("Receive request: /api/v1/apps/install")
    ret = manage.install_app(app_name, customer_app_name, app_version)
    return JSONResponse(content=ret)


@router.api_route("/process", methods=["GET", "POST"], summary="获取指定APP的安装进度", response_description=rd,
                  response_model=Response)
def install_app_process(app_id: Optional[str] = Query(default=None, description="应用ID")):
    myLogger.info_logger("Receive request: /api/v1/apps/process")
    ret = manage.install_app_process(app_id)
    return JSONResponse(content=ret)


@router.api_route("/start", methods=["GET", "POST"], summary="启动APP", response_description=rd, response_model=Response)
def start_app(app_id: Optional[str] = Query(default=None, description="应用ID")):
    myLogger.info_logger("Receive request: /api/v1/apps/start")
    ret = manage.start_app(app_id)
    return JSONResponse(content=ret)


@router.api_route("/stop", methods=["GET", "POST"], summary="停止APP", response_description=rd, response_model=Response)
def stop_app(app_id: Optional[str] = Query(default=None, description="应用ID")):
    myLogger.info_logger("Receive request: /api/v1/apps/stop")
    ret = manage.stop_app(app_id)
    return JSONResponse(content=ret)


@router.api_route("/restart", methods=["GET", "POST"], summary="重启APP", response_description=rd,
                  response_model=Response)
def restart_app(app_id: Optional[str] = Query(default=None, description="应用ID")):
    myLogger.info_logger("Receive request: /api/v1/apps/restart")
    ret = manage.restart_app(app_id)
    return JSONResponse(content=ret)


@router.api_route("/uninstall", methods=["GET", "POST"], summary="卸载APP", response_description=rd,
                  response_model=Response)
def uninstall_app(app_id: Optional[str] = Query(default=None, description="应用ID")):
    myLogger.info_logger("Receive request: /api/v1/apps/uninstall")
    ret = manage.uninstall_app(app_id)
    return JSONResponse(content=ret)
