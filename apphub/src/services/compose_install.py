import yaml

from src.core.exception import CustomException
from src.schemas.appComposeInstall import ComposeValidationRequest, ComposeValidationResponse


def validate_compose_installation(payload: ComposeValidationRequest) -> ComposeValidationResponse:
    try:
        compose_content = yaml.safe_load(payload.compose_content)
    except yaml.YAMLError as exc:
        raise CustomException(400, "Invalid Request", f"Compose syntax is invalid: {exc}")

    if not isinstance(compose_content, dict):
        raise CustomException(400, "Invalid Request", "Compose content must decode to an object.")

    services = compose_content.get("services")
    if not isinstance(services, dict) or not services:
        raise CustomException(400, "Invalid Request", "Compose content must define at least one service.")

    service_names = [str(name).strip() for name in services.keys() if str(name).strip()]
    if len(service_names) != len(services):
        raise CustomException(400, "Invalid Request", "Compose services must use non-empty names.")

    return ComposeValidationResponse(
        valid=True,
        services=service_names,
        environment_keys=[entry.key for entry in payload.env],
        details=f"Compose content is valid with {len(service_names)} service(s).",
    )