import asyncio
import datetime
from http.client import HTTPException
import json
import time
from typing import Any, Dict
from fastapi import APIRouter, Query,Path
from fastapi.responses import StreamingResponse
from src.core import logger
from src.core.exception import CustomException
from src.schemas.appAvailable import AppAvailableResponse
from src.schemas.appCatalog import AppCatalogResponse
from src.schemas.appInstall import appInstall
from src.schemas.appResponse import AppResponse
from src.schemas.errorResponse import ErrorResponse
from src.services.app_manager import AppManger
from src.services.common_check import install_validate
from threading import Thread

router = APIRouter()

@router.get(
        "/apps/catalog/{locale}",
        summary="List Catalogs",
        description="List all app's catalogs",
        responses={
        200: {"model": list[AppCatalogResponse]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        }
    )
def get_catalog_apps(
    locale: str = Path(..., description="Language to get catalogs from", regex="^(zh|en)$"),
):
    return AppManger().get_catalog_apps(locale)

@router.get(
        "/apps/available/{locale}",
        summary="List Available Apps",
        description="List all available apps",
        responses={
        200: {"model": list[AppAvailableResponse]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        }
    )
def get_available_apps(
    locale: str = Path(..., description="Language to get available apps from", regex="^(zh|en)$"),
):
    return AppManger().get_available_apps(locale)

@router.get(
        "/apps",
        summary="List Installed Apps",
        description="List all installed apps",
        responses={
        200: {"model": list[AppResponse]},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        }
    )
def get_apps(
    endpointId: int = Query(None, description="Endpoint ID to get apps from. If not set, get apps from the local endpoint")
):
    return AppManger().get_apps(endpointId)

@router.get(
        "/apps/{app_id}",
        summary="Inspect App",
        description="Retrieve details about an app",
        responses={
        200: {"model": AppResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
    )
def get_app_by_id(
    app_id: str = Path(..., description="App ID to get details from"),
    endpointId: int = Query(None, description="Endpoint ID to get app details from. If not set, get details from the local endpoint")
):
    return AppManger().get_app_by_id(app_id, endpointId)

@router.post(
    "/apps/install",
    summary="Install App",
    response_model_exclude_defaults=True, 
    description="Install an app on an endpoint",
    responses={
        200: {"description": "Success"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def apps_install(
    appInstall: appInstall,
    endpointId: int = Query(None, description="Endpoint ID to install app on,if not set, install on the local endpoint"),
):
    # install validate
    install_validate(appInstall,endpointId)

    # install app
    Thread(target=AppManger().install_app, args=(appInstall, endpointId)).start()
    
    # return success
    return ErrorResponse(
        status_code=200,
        message="Success",
        details="The app is installing and can be viewed through 'My Apps.'",
    )

    # async def log_generator(queue: asyncio.Queue):
    #     while True:
    #         message = await queue.get()
    #         if message is None:
    #             break
    #         yield f"{message}\n"

    # queue = asyncio.Queue()
    # app_manager = AppManger()
    # asyncio.create_task(app_manager.install_app(appInstall, endpointId, queue))
    # return StreamingResponse(log_generator(queue), media_type="text/plain",status_code=200)


@router.post(
    "/apps/{app_id}/start",
    summary="Start App",
    description="Start an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App started successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_start(
    app_id: str = Path(..., description="App ID to start"),
    endpointId: int = Query(None, description="Endpoint ID to start app on. If not set, start on the local endpoint")
):
    AppManger().start_app(app_id, endpointId)


@router.post(
    "/apps/{app_id}/stop",
    summary="Stop App",
    response_model_exclude_defaults=True, 
    description="Stop an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App stopped successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_stop(
    app_id: str = Path(..., description="App ID to stop"),
    endpointId: int = Query(None, description="Endpoint ID to stop app on. If not set, stop on the local endpoint"),
):
    AppManger().stop_app(app_id, endpointId)

@router.post(
    "/apps/{app_id}/restart",
    summary="Restart App",
    response_model_exclude_defaults=True, 
    description="Restart an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App restarted successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_restart(
    app_id: str = Path(..., description="App ID to restart"),
    endpointId: int = Query(None, description="Endpoint ID to Restart app on. If not set, Restart on the local endpoint"),
):
    AppManger().restart_app(app_id, endpointId)

@router.put(
    "/apps/{app_id}/redeploy",
    summary="Redeploy App",
    response_model_exclude_defaults=True, 
    description="Redeploy an app on an endpoint",
    # status_code=200,
    responses={
        200: {"description": "Success"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def app_redeploy(
    app_id: str = Path(..., description="App ID to redeploy"),
    endpointId: int = Query(None, description="Endpoint ID to redeploy app on. If not set, redeploy on the local endpoint"),
    pullImage: bool = Query(..., description="Whether to pull the image when redeploying the app"),
):

    async def log_generator(queue: asyncio.Queue):
        error_occurred = False
        try:
            while True:
                item = await queue.get()
                
                # 构建基础消息结构
                log_entry: Dict[str, Any] = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "type": "log",
                    "data": None
                }

                # 处理不同消息类型
                if isinstance(item, dict):
                    if item.get("type") == "error":
                        log_entry.update({
                            "type": "error",
                            "code": item.get("code", 500),
                            "message": item.get("message", "Unknown error"),
                            "details": item.get("details")
                        })
                        error_occurred = True
                    elif item.get("type") == "end":
                        log_entry["type"] = "end"
                    else:
                        log_entry["data"] = item
                elif isinstance(item, CustomException):
                    log_entry.update({
                        "type": "error",
                        "code": item.status_code,
                        "message": item.message,
                        "details": item.details
                    })
                    error_occurred = True
                else:
                    log_entry["data"] = str(item)

                # 序列化并发送
                yield json.dumps(log_entry) + "\n"

                # 错误或结束信号后终止
                if error_occurred or log_entry["type"] == "end":
                    break
        finally:
            # 记录最终状态
            final_status = {
                "status": "failed" if error_occurred else "success",
                "timestamp": datetime.datetime.now().isoformat()
            }
            yield json.dumps(final_status) + "\n"

    async def task_wrapper():
        try:
            # 成功执行后发送明确的结束标记
            await app_manager.redeploy_app(
                app_id, 
                pullImage, 
                endpointId, 
                queue=queue
            )
            await queue.put({"type": "end"})
        except CustomException as e:
            # 标准化错误格式
            await queue.put({
                "type": "error",
                "code": e.status_code,
                "message": e.message,
                "details": e.details,
                "timestamp": datetime.datetime.now().isoformat()  # 添加时间戳
            })
        except Exception as e:
            # 处理未预期的异常类型
            await queue.put({
                "type": "error",
                "code": 500,
                "message": "Internal Server Error",
                "details": f"{type(e).__name__}: {str(e)}",
                "timestamp": datetime.datetime.now().isoformat()
            })
        finally:
            # 确保流结束
            await queue.put({"type": "end"})  # 冗余保障

    queue = asyncio.Queue(maxsize=100)
    app_manager = AppManger()

    asyncio.create_task(task_wrapper())
    #asyncio.create_task(app_manager.redeploy_app(app_id, pullImage,endpointId,queue))
    return StreamingResponse(log_generator(queue), media_type="text/plain")


@router.delete(
    "/apps/{app_id}/uninstall",
    summary="Uninstall App",
    description="Uninstall an app on an endpoint",
    status_code=204,
    responses={
        204: {"description": "App uninstalled successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
def apps_uninstall(
    app_id: str=Path(..., description="App ID to uninstall"),
    endpointId: int = Query(None, description="Endpoint ID to uninstall app on,if not set, uninstall on the local endpoint"),
    purge_data: bool = Query(..., description="Whether to purge data when uninstalling the app")
):
    AppManger().uninstall_app(app_id,purge_data, endpointId)


@router.delete(
    "/apps/{app_id}/remove",
    summary="Remove App",
    response_model_exclude_defaults=True, 
    description="Remove an app on an endpoint where the app is empty(status is 'inactive')",
    status_code=204,
    responses={
        204: {"description": "App removed successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_remove(
    app_id: str = Path(..., description="App ID to remove"),
    endpointId: int = Query(None, description="Endpoint ID to remove app on. If not set, remove on the local endpoint"),
):
    AppManger().remove_app(app_id, endpointId)

@router.delete(
    "/apps/{app_id}/error/remove",
    summary="Remove Error App",
    response_model_exclude_defaults=True, 
    description="Remove an app on an endpoint where the app is error(status is 'error')",
    status_code=204,
    responses={
        204: {"description": "App removed successfully"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def app_remove(
    app_id: str = Path(..., description="The error app ID to remove"),
):
    AppManger().remove_error_app(app_id)
