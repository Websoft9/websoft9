from typing import Optional, List

from fastapi import APIRouter, status, Depends, Query, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse
import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.model.app import App
from api.model.response import Response
from api.service import manage
from api.utils import shell_execute, const
from api.utils.common_log import myLogger
from api.exception.command_exception import CommandException

router = APIRouter()

rd_s = "ResponseData: 各个接口的业务数据\n\n{\n\n"
rd_m = "&emsp;&emsp;AppID：应用ID\n\n}\n\n"
rd_e = "Error：错误code和错误信息\n\n{\n\n" \
       "&emsp;&emsp;Code：错误码,\n\n" \
       "&emsp;&emsp;Message：错误信息,\n\n" \
       "&emsp;&emsp;Detail：错误详情\n\n}"

rd_status = "&emsp;&emsp;app_id：应用ID\n\n" \
            "&emsp;&emsp;status：应用运行状态,[installing(创建中)，running(运行中)，exited(停止)，restarting(反复重启)，failed(失败)]\n\n" \
         "&emsp;&emsp;StatusReason：{\n\n" \
         "&emsp;&emsp;&emsp;&emsp;Code：错误代码,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;Message：错误提示信息,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;Detail：错误真实信息\n\n&emsp;&emsp;}\n\n}\n\n"
info = "&emsp;&emsp;app_id：应用ID,\n\n&emsp;&emsp;app_name：应用名,\n\n" \
         "&emsp;&emsp;customer_name：自定义应用名,\n\n&emsp;&emsp;trade_mark：应用商标,\n\n" \
         "&emsp;&emsp;status：应用运行状态,[installing(创建中)，running(运行中)，exited(停止)，restarting(反复重启)，failed(失败)]\n\n" \
         "&emsp;&emsp;StatusReason：{\n\n" \
         "&emsp;&emsp;&emsp;&emsp;Code：错误代码,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;Message：错误提示信息,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;Detail：错误真实信息\n\n&emsp;&emsp;}\n\n" \
         "&emsp;&emsp;official_app：是否为官方应用,\n\n" \
         "&emsp;&emsp;app_version：应用版本,\n\n" \
         "&emsp;&emsp;create_time：应用创建时间,\n\n" \
         "&emsp;&emsp;volume_data：数据目录,\n\n" \
         "&emsp;&emsp;config_path：配置目录,\n\n" \
         "&emsp;&emsp;image_url：图片路径,\n\n" \
         "&emsp;&emsp;app_https：是否为https,\n\n" \
         "&emsp;&emsp;app_replace_url：是否有替代网址,\n\n" \
         "&emsp;&emsp;config：{\n\n" \
         "&emsp;&emsp;&emsp;&emsp;port：应用端口,\n\n&emsp;&emsp;&emsp;&emsp;compose_file：docker compose 文件路径,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;url：应用网址,\n\n&emsp;&emsp;&emsp;&emsp;admin_url：管理员网址,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;admin_path：后台后缀,\n\n&emsp;&emsp;&emsp;&emsp;admin_username：管理员用户名,\n\n&emsp;&emsp;&emsp;&emsp;admin_password：管理员密码,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;admin_domain_url：后台域名访问地址,\n\n&emsp;&emsp;&emsp;&emsp;default_domain：默认域名}\n\n}\n\n"

domain = "&emsp;&emsp;Domain_set：{\n\n" \
         "&emsp;&emsp;&emsp;&emsp;domains：域名列表\n\n" \
         "&emsp;&emsp;&emsp;&emsp;default_domain：默认域名\n\n&emsp;&emsp;}\n\n}\n\n"

update = "&emsp;&emsp;Compare_content: 新旧版本内容{\n\n" \
         "&emsp;&emsp;&emsp;&emsp;current_version: 当前版本,\n\n" \
         "&emsp;&emsp;&emsp;&emsp;Update_content: {\n\n" \
         "&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;version: 最新版本\n\n" \
         "&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;date: 更新日期\n\n" \
         "&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;content: 更新内容\n\n&emsp;&emsp;&emsp;&emsp;}\n\n&emsp;&emsp;}\n\n}\n\n"

appstore_update = "&emsp;&emsp;Update_content: [] 更新内容\n\n}\n\n"
auto = "&emsp;&emsp;auto_update: 目前的自动更新状态\n\n}\n\n"

rd = rd_s + rd_m + rd_e
rd_info = rd_s + info + rd_e
rd_status = rd_s + rd_status + rd_e
rd_domain = rd_s + domain + rd_e
rd_update_list = rd_s + update + rd_e
rd_appstore = rd_s + appstore_update + rd_e
rd_auto_list = rd_s + auto + rd_e

@router.api_route("/AppStatus", methods=["GET", "POST"], summary="获取指定APP的信息",
                  response_description=rd_status,
                  response_model=Response)
def AppStatus(request: Request,app_id: Optional[str] = Query(default=None, description="应用ID")):
    try:
        myLogger.info_logger("Receive request: /AppStatus")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = manage.get_app_status(app_id)
    except CommandException as ce:
        myLogger.info_logger(ce.message)
        ret = {}
        ret['ResponseData'] = None
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        myLogger.info_logger(e)
        ret = {}
        ret['ResponseData'] = None
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
    return JSONResponse(ret)


@router.api_route("/AppList", methods=["GET", "POST"], summary="获取所有APP的信息", response_description=rd_info,
                  response_model=Response)
def AppList(request: Request, app_id: Optional[str] = Query(default=None, description="应用ID")):
    try:
        myLogger.info_logger("Receive request: /AppList")
        get_headers(request)
        app_list = manage.get_my_app(app_id)
        myLogger.info_logger(len(app_list))
        response = JSONResponse({'ResponseData': app_list})
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = None
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
        response = JSONResponse(content=ret)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = None
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
        response = JSONResponse(content=ret)
    return response


@router.api_route("/AppInstall", methods=["GET", "POST"], summary="安装APP", response_description=rd,
                  response_model=Response)
def AppInstall(request: Request, app_name: Optional[str] = Query(default=None, description="应用名称"),
               customer_app_name: Optional[str] = Query(default=None, description="用户自定义应用名称"),
               app_version: Optional[str] = Query(default=None, description="应用版本")):
    try:
        myLogger.info_logger("Receive request: /AppInstall")
        get_headers(request)
        ret = manage.install_app(app_name, customer_app_name, app_version)
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_name + "_" + customer_app_name
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
        myLogger.error_logger("Ready for return fail message")
    except Exception as e:
        myLogger.error_logger(str(e))
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_name + "_" + customer_app_name
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))

    myLogger.info_logger(ret)
    return JSONResponse(content=ret)


@router.api_route("/AppStart", methods=["GET", "POST"], summary="启动APP", response_description=rd,
                  response_model=Response)
def AppStart(request: Request,app_id: Optional[str] = Query(default=None, description="应用ID")):
    try:
        myLogger.info_logger("Receive request: /AppStart")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        manage.start_app(app_id)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        myLogger.info_logger("AppStart commond error")
        myLogger.info_logger(ce.detail)
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
    return JSONResponse(content=ret)


@router.api_route("/AppStop", methods=["GET", "POST"], summary="停止APP", response_description=rd,
                  response_model=Response)
def AppStop(request: Request,app_id: Optional[str] = Query(default=None, description="应用ID")):
    try:
        myLogger.info_logger("Receive request: /AppStop")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        manage.stop_app(app_id)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
    return JSONResponse(content=ret)


@router.api_route("/AppRestart", methods=["GET", "POST"], summary="重启APP", response_description=rd,
                  response_model=Response)
def AppRestart(request: Request,app_id: Optional[str] = Query(default=None, description="应用ID")):
    try:
        myLogger.info_logger("Receive request: /AppRestart")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        manage.restart_app(app_id)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
    return JSONResponse(content=ret)


@router.api_route("/AppUninstall", methods=["GET", "POST"], summary="卸载APP", response_description=rd,
                  response_model=Response)
def AppUninstall(request: Request, app_id: Optional[str] = Query(default=None, description="应用ID")):

    try:
        myLogger.info_logger("Receive request: /AppUninstall")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        manage.uninstall_app(app_id)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))

    return JSONResponse(content=ret)

@router.api_route("/AppDomainAdd", methods=["GET", "POST"], summary="绑定域名",  response_model=Response, response_description=rd)
def AppDomainAdd(request: Request, app_id: Optional[str] = Query(default=None, description="应用ID"), domains: Optional[str] = Query(default=None, description="域名")):

    try:
        myLogger.info_logger("Receive request: /AppDomainAdd")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        manage.app_domain_add(app_id,domains)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))

    return JSONResponse(content=ret)

@router.api_route("/AppDomainUpdate", methods=["GET", "POST"], summary="修改域名",  response_model=Response, response_description=rd)
def AppDomainUpdate(request: Request, app_id: Optional[str] = Query(default=None, description="应用ID"), domain_old: Optional[str] = Query(default=None, description="原域名"), domain_new: Optional[str] = Query(default=None, description="新域名")):

    try:
        myLogger.info_logger("Receive request: /AppDomainUpdate")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        domains = manage.app_domain_update(app_id,domain_old,domain_new)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))

    return JSONResponse(content=ret)

@router.api_route("/AppDomainDelete", methods=["GET", "POST"], summary="删除域名",  response_model=Response, response_description=rd)
def AppDomainDelete(request: Request, app_id: Optional[str] = Query(default=None, description="应用ID"), domain: Optional[str] = Query(default=None, description="删除域名")):

    try:
        myLogger.info_logger("Receive request: /AppDomainDelete")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        manage.app_domain_delete(app_id,domain)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))

    return JSONResponse(content=ret)

@router.api_route("/AppDomainSet", methods=["GET", "POST"], summary="设定域名",  response_model=Response, response_description=rd)
def AppDomainSet(request: Request, app_id: Optional[str] = Query(default=None, description="应用ID"), domain: Optional[str] = Query(default=None, description="域名")):

    try:
        myLogger.info_logger("Receive request: /AppDomainSet")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        manage.app_domain_set(domain,app_id)
        ret['ResponseData']['AppID'] = app_id
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))

    return JSONResponse(content=ret)

@router.api_route("/AppDomainList", methods=["GET", "POST"], summary="查询App对应域名",  response_model=Response, response_description=rd_domain)
def AppDomainList(request: Request, app_id: Optional[str] = Query(default=None, description="应用ID")):

    try:
        myLogger.info_logger("Receive request: /AppDomainList")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        domain_set = manage.app_domain_list(app_id)
        ret['ResponseData']['Domain_set'] = domain_set
        myLogger.info_logger(ret)
        response = JSONResponse(content=ret)
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
        response = JSONResponse(content=ret)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['AppID'] = app_id
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
        response = JSONResponse(content=ret)

    return response

@router.api_route("/AppUpdateList", methods=["GET", "POST"], summary="查询更新內容", response_model=Response, response_description=rd_update_list)
def AppUpdateList(request: Request):

    try:
        myLogger.info_logger("Receive request: /AppUpdateList")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['Compare_content'] = manage.get_update_list()
        myLogger.info_logger(ret)
        response = JSONResponse(content=ret)
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
        response = JSONResponse(content=ret)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
        response = JSONResponse(content=ret)

    return response

@router.api_route("/AppStoreUpdate", methods=["GET", "POST"], summary="更新软件商店", response_model=Response, response_description=rd_appstore)
def AppStoreUpdate(request: Request):

    try:
        myLogger.info_logger("Receive request: /AppStoreUpdate")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['Update_content'] = manage.AppStoreUpdate()
        myLogger.info_logger(ret)
        response = JSONResponse(content=ret)
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
        response = JSONResponse(content=ret)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
        response = JSONResponse(content=ret)

    return response

@router.api_route("/AppAutoUpdate", methods=["GET", "POST"], summary="软件商店自动更新", response_model=Response, response_description=rd_auto_list)
def AppAutoUpdate(request: Request,auto_update: Optional[str] = Query(default=None, description="自动更新标志(可选值:true,false,None)")):

    try:
        myLogger.info_logger("Receive request: /AppAutoUpdate")
        get_headers(request)
        ret = {}
        ret['ResponseData'] = {}
        ret['ResponseData']['auto_update'] = manage.AppAutoUpdate(auto_update)
        response = JSONResponse(content=ret)
    except CommandException as ce:
        ret = {}
        ret['ResponseData'] = {}
        ret['Error'] = manage.get_error_info(ce.code, ce.message, ce.detail)
        response = JSONResponse(content=ret)
    except Exception as e:
        ret = {}
        ret['ResponseData'] = {}
        ret['Error'] = manage.get_error_info(const.ERROR_SERVER_SYSTEM, "system original error", str(e))
        response = JSONResponse(content=ret)

    return response

def get_headers(request):
    headers = request.headers
    try:
        version = headers.get('Version')
        language = headers.get('Language')
        myLogger.info_logger("Version: " + version + ", Language: " + language)
    except:
        pass
