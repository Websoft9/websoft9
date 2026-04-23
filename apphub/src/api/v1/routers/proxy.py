
from typing import List, Optional
from fastapi import APIRouter, Query,Path,Request,Depends
from fastapi.params import Body
from src.schemas.errorResponse import ErrorResponse
from src.schemas.proxyHosts import ProxyHost
from src.schemas.proxyTask import ProxyMutationRequest, ProxyTaskAcceptedResponse, ProxyTaskStatusResponse
from src.services.app_manager import AppManger
from src.services.proxy_task_manager import ProxyTaskManager
from src.services.proxy_manager import ProxyManager
from src.core.logger import logger

router = APIRouter()

@router.get(
            "/proxys/{app_id}",
            summary="Get Proxys",
            description="Get proxys by app",
            responses={
                200: {"model": list[ProxyHost]},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def get_proxys(
        app_id: str = Path(..., description="App ID to get proxys from"),
        endpointId: int = Query(None, description="Endpoint ID to get proxys from. If not set, get proxys from the local endpoint")
    ):
    proxy_hosts = AppManger().get_proxys_by_app(app_id,endpointId)
    return [ProxyManager.to_proxy_host_response(proxy_host) for proxy_host in proxy_hosts]

@router.get(
            "/proxys/tasks/{task_id}",
            summary="Get proxy task status",
            description="Get proxy task status by task id",
            responses={
                200: {"model": ProxyTaskStatusResponse},
                400: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def get_proxy_task(task_id: str = Path(..., description="Proxy task id")):
    return ProxyTaskManager().get_task(task_id)

@router.get(
            "/proxys/ssl/certificates",
            summary="Get SSL Certificates",
            description="Get all ssl certificates",
            responses={
                200: {"model": list[dict]},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def get_certificates():
    return ProxyManager().get_all_certificates()

@router.post(
            "/proxys/{app_id}",
            summary="Create Proxy",
            description="Create a proxy host",
            responses={
                200: {"model": list[ProxyHost]},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def create_proxys(
    proxy_request: ProxyMutationRequest = Body(..., description="Proxy mutation request", example={"domain_names": ["example1.com","example2.com"], "certificate_id": 0}),
    app_id: str = Path(..., description="App ID to create proxys from"),
    endpointId: int = Query(None, description="Endpoint ID to create proxys from. If not set, create proxys from the local endpoint"),
    async_task: bool = Query(False, description="Submit the proxy mutation as an async task"),
):
    if async_task:
        task_id = ProxyTaskManager().submit_create_task(app_id, proxy_request.domain_names, proxy_request.certificate_id, endpointId)
        return ProxyTaskAcceptedResponse(task_id=task_id)

    result = AppManger().create_proxy_by_app(app_id,proxy_request.domain_names,endpointId,proxy_request.certificate_id)
    return ProxyManager.to_proxy_host_response(result)
    
@router.put(
            "/proxys/{proxy_id}",
            summary="Update Proxys",
            description="Update proxys by app",
            responses={
                200: {"model": list[ProxyHost]},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def update_proxys(
    proxy_request: ProxyMutationRequest = Body(..., description="Proxy mutation request", example={"domain_names": ["example1.com","example2.com"], "certificate_id": 0}),
    proxy_id: int = Path(..., description="Proxy ID to update proxys from"),
    endpointId: int = Query(None, description="Endpoint ID to create proxys from. If not set, create proxys from the local endpoint"),
    async_task: bool = Query(False, description="Submit the proxy mutation as an async task"),
):
    if async_task:
        task_id = ProxyTaskManager().submit_update_task(proxy_id, proxy_request.domain_names, proxy_request.certificate_id, endpointId)
        return ProxyTaskAcceptedResponse(task_id=task_id)

    result = AppManger().update_proxy_by_app(proxy_id,proxy_request.domain_names,endpointId,proxy_request.certificate_id)
    return ProxyManager.to_proxy_host_response(result)

# @router.delete(
#             "/proxys/app/{app_id}",
#             summary="Delete Proxys",
#             description="Delete proxys by app",
#             status_code=204,
#             responses={
#                 204: {"description": "Delete Proxys Success"},
#                 400: {"model": ErrorResponse},
#                 500: {"model": ErrorResponse},
#             }
#         )
# def delete_proxys_by_app(
#     app_id: str = Path(..., description="App ID to create proxys from"),
#     endpointId: int = Query(None, description="Endpoint ID to create proxys from. If not set, create proxys from the local endpoint"),
# ):
#     AppManger().remove_proxy_by_app(app_id,endpointId)

@router.delete(
            "/proxys/{proxy_id}",
            summary="Delete Proxys",
            description="Delete proxys by proxy_id",
            status_code=204,
            responses={
                204: {"description": "Delete Proxys Success"},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def delete_proxys_by_id(
    request: Request,
    proxy_id: int = Path(..., description="Proxy ID to delete proxys from")
    
):
    client_host = request.headers.get("Host")
    # client_host = request.client.host
    AppManger().remove_proxy_by_id(proxy_id,client_host)


