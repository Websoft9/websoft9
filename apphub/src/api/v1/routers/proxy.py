
from typing import List, Optional
from fastapi import APIRouter, Query,Path
from fastapi.params import Body
from src.schemas.domainNames import DomainNames
from src.schemas.errorResponse import ErrorResponse
from src.schemas.proxyHosts import ProxyHost
from src.services.app_manager import AppManger


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
    return AppManger().get_proxys_by_app(app_id,endpointId)

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
    domain_names: DomainNames = Body(..., description="Domain names to create proxys from", example={"domain_names": ["example1.com","example2.com"]}),
    app_id: str = Path(..., description="App ID to create proxys from"),
    endpointId: int = Query(None, description="Endpoint ID to create proxys from. If not set, create proxys from the local endpoint"),
):
    return AppManger().create_proxy_by_app(app_id,domain_names.domain_names,endpointId)
    
@router.put(
            "/proxys/{app_id}}",
            summary="Update Proxys",
            description="Update proxys by app",
            responses={
                200: {"model": list[ProxyHost]},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def update_proxys(
    proxyHost:ProxyHost = Body(..., description="Proxy host to update proxys from"),
    app_id: str = Path(..., description="App ID to create proxys from"),
    endpointId: int = Query(None, description="Endpoint ID to create proxys from. If not set, create proxys from the local endpoint"),
):
    return AppManger().update_proxy_by_app(app_id,proxyHost,endpointId)

@router.delete(
            "/proxys/app/{app_id}",
            summary="Delete Proxys",
            description="Delete proxys by app",
            status_code=204,
            responses={
                204: {"description": "Delete Proxys Success"},
                400: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            }
        )
def delete_proxys_by_app(
    app_id: str = Path(..., description="App ID to create proxys from"),
    endpointId: int = Query(None, description="Endpoint ID to create proxys from. If not set, create proxys from the local endpoint"),
):
    AppManger().remove_proxy_by_app(app_id,endpointId)

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
    proxy_id: int = Path(..., description="Proxy ID to delete proxys from")
):
    AppManger().remove_proxy_by_id(proxy_id)