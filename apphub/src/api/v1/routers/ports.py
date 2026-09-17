from fastapi import APIRouter, Query

from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.schemas.portAllocation import PortCheckResponse, PortSuggestRequest, PortSuggestResponse

from src.services.port_allocator import check_ports, suggest_ports

router = APIRouter()


@router.post(
    "/ports/suggest",
    summary="Suggest free host ports",
    description="Assign free host ports from the configured range for app installation settings, in display order.",
    responses={
        200: {"model": PortSuggestResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def suggest_install_ports(payload: PortSuggestRequest):
    keys = [item.key for item in payload.ports]
    return {"suggestions": suggest_ports(keys)}


@router.get(
    "/ports/check",
    summary="Check host port availability",
    description="Check whether the given host ports are already claimed by containers or installing apps.",
    responses={
        200: {"model": PortCheckResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def check_host_ports(
    ports: str = Query(..., description="Comma-separated host port list, e.g. 9001,9002"),
):
    parsed_ports: list[int] = []
    for raw_port in ports.split(","):
        raw_port = raw_port.strip()
        if not raw_port:
            continue
        if not raw_port.isdigit():
            raise CustomException(400, "Invalid Request", f"Invalid port: {raw_port}")
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise CustomException(400, "Invalid Request", f"Port out of range: {raw_port}")
        parsed_ports.append(port)

    if not parsed_ports:
        raise CustomException(400, "Invalid Request", "No ports provided")

    return {"results": check_ports(parsed_ports)}
