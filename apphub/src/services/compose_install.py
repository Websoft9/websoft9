import os
import random
import shutil
import tempfile
import json
from datetime import datetime

import yaml

from src.core.exception import CustomException
from src.core.logger import logger
from src.schemas.appComposeInstall import ComposeInstallAcceptedResponse, ComposeInstallRequest, ComposeValidationRequest, ComposeValidationResponse
from src.services.app_manager import AppManger
from src.services.app_status import add_installing_logs, modify_app_information, remove_app_installation, remove_installation_logs, start_app_installation
from src.services.gitea_manager import GiteaManager
from src.services.integration_credentials import IntegrationCredentialProvider
from src.services.portainer_manager import PortainerManager
from src.services.proxy_manager import ProxyManager
from src.utils.file_manager import FileHelper
from src.utils.password_generator import PasswordGenerator


COMPOSE_METADATA_PATH = ".websoft9/compose-metadata.json"


def _validate_service_spec(services: dict) -> None:
    """Validate that service fields match Docker Compose schema types."""
    # These fields must be a list or mapping — not a plain scalar
    list_or_dict_fields = ['environment', 'volumes', 'labels', 'extra_hosts', 'sysctls', 'ulimits', 'depends_on']
    # These fields must be a list
    list_only_fields = ['ports', 'expose']
    for service_name, service_spec in services.items():
        if not isinstance(service_spec, dict):
            raise CustomException(
                400, "Invalid Request",
                f"Service '{service_name}' must be a mapping."
            )
        for field in list_or_dict_fields:
            if field in service_spec and service_spec[field] is not None:
                val = service_spec[field]
                if not isinstance(val, (list, dict)):
                    raise CustomException(
                        400, "Invalid Request",
                        f"Service '{service_name}': field '{field}' must be a list or mapping, not a {type(val).__name__}. "
                        f"Tip: list items need a leading '- ' dash."
                    )
        for field in list_only_fields:
            if field in service_spec and service_spec[field] is not None:
                val = service_spec[field]
                if not isinstance(val, list):
                    raise CustomException(
                        400, "Invalid Request",
                        f"Service '{service_name}': field '{field}' must be a list, not a {type(val).__name__}. "
                        f"Tip: list items need a leading '- ' dash."
                    )


def _check_variable_interpolation(compose_content: str) -> None:
    """Detect unclosed ${...} variable substitution patterns that Docker Compose would reject."""
    for line_no, line in enumerate(compose_content.split('\n'), 1):
        pos = 0
        while True:
            start = line.find('${', pos)
            if start == -1:
                break
            close = line.find('}', start + 2)
            if close == -1:
                snippet = line[start:].rstrip()
                raise CustomException(
                    400, "Invalid Request",
                    f"Line {line_no}: unclosed variable substitution '{snippet}' — "
                    f"expected closing '}}'. Use '${{VAR_NAME}}' format."
                )
            pos = close + 1


def _load_compose_document(compose_content: str) -> dict:
    _check_variable_interpolation(compose_content)
    try:
        compose_document = yaml.safe_load(compose_content)
    except yaml.YAMLError as exc:
        raise CustomException(400, "Invalid Request", f"Compose syntax is invalid: {exc}")

    if not isinstance(compose_document, dict):
        raise CustomException(400, "Invalid Request", "Compose content must decode to an object.")

    services = compose_document.get("services")
    if not isinstance(services, dict) or not services:
        raise CustomException(400, "Invalid Request", "Compose content must define at least one service.")

    _validate_service_spec(services)

    return compose_document


def _get_service_names(compose_document: dict) -> list[str]:
    services = compose_document.get("services")
    if not isinstance(services, dict) or not services:
        raise CustomException(400, "Invalid Request", "Compose content must define at least one service.")

    service_names = [str(name).strip() for name in services.keys() if str(name).strip()]
    if len(service_names) != len(services):
        raise CustomException(400, "Invalid Request", "Compose services must use non-empty names.")

    return service_names


def _extract_forward_port(compose_document: dict) -> int | None:
    services = compose_document.get("services") or {}
    for service in services.values():
        if not isinstance(service, dict):
            continue
        for port in service.get("ports") or []:
            if isinstance(port, int):
                return port
            if isinstance(port, str):
                normalized = port.split("/")[0].strip()
                parts = [part.strip() for part in normalized.split(":") if part.strip()]
                target = parts[-1] if parts else ""
                if target.isdigit():
                    return int(target)
            if isinstance(port, dict):
                target = port.get("target")
                try:
                    return int(target)
                except (TypeError, ValueError):
                    continue
    return None


def validate_compose_installation(payload: ComposeValidationRequest) -> ComposeValidationResponse:
    compose_document = _load_compose_document(payload.compose_content)
    service_names = _get_service_names(compose_document)

    return ComposeValidationResponse(
        valid=True,
        services=service_names,
        environment_keys=[entry.key for entry in payload.env],
        details=f"Compose content is valid with {len(service_names)} service(s).",
    )


def prepare_compose_install_tracking(payload: ComposeInstallRequest) -> tuple[str, str]:
    tracked_app_id = f"{payload.app_id}_{PasswordGenerator.generate_random_string(5)}"
    tracking_id = start_app_installation(tracked_app_id, payload.app_id)
    return tracked_app_id, tracking_id


def install_compose_application(payload: ComposeInstallRequest, endpoint_id: int | None = None, tracked_app_id: str | None = None, tracking_id: str | None = None) -> None:
    compose_document = _load_compose_document(payload.compose_content)
    _get_service_names(compose_document)
    forward_port = _extract_forward_port(compose_document)
    app_id = tracked_app_id or payload.app_id
    install_tracking_id = tracking_id or start_app_installation(app_id, payload.app_id)
    compose_manager = AppManger()
    portainer_manager = PortainerManager()
    gitea_manager = GiteaManager()
    repo_url = None
    workspace_path = None

    if endpoint_id is None:
        endpoint_id = portainer_manager.get_local_endpoint_id()

    try:
        add_installing_logs(install_tracking_id, "Initializing installation", "")
        repo_url = gitea_manager.create_repo(app_id)

        temp_root = tempfile.mkdtemp(prefix=f"compose-{payload.app_id}-")
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S%f")
        workspace_path = os.path.join(temp_root, f"{payload.app_id}_{timestamp_str}_{random.randint(1000, 9999)}")
        os.makedirs(workspace_path, exist_ok=True)

        FileHelper.write_file(os.path.join(workspace_path, "docker-compose.yml"), payload.compose_content)

        env_lines = [f"{entry.key}={entry.value}" for entry in payload.env]
        FileHelper.write_file(os.path.join(workspace_path, ".env"), "\n".join(env_lines) + "\n")

        metadata_path = os.path.join(workspace_path, COMPOSE_METADATA_PATH)
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        FileHelper.write_file(
            metadata_path,
            json.dumps(
                {
                    "dist": "compose",
                    "app_name": payload.app_id,
                    "version": "custom",
                    "domain": payload.domain,
                    "tracked_app_id": app_id,
                },
                ensure_ascii=True,
                indent=2,
            ) + "\n",
        )

        for mount in payload.mounts:
            target_path = os.path.join(workspace_path, mount.path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            FileHelper.write_file(target_path, mount.content)

        compose_manager._init_local_repo_and_push_to_remote(workspace_path, repo_url)

        add_installing_logs(install_tracking_id, "Pulling docker image", "")
        compose_manager.pull_images_from_yml(workspace_path, install_tracking_id)

        add_installing_logs(install_tracking_id, "Starting the services", "")
        credentials = IntegrationCredentialProvider().get_gitea_credentials()
        stack_info = portainer_manager.create_stack_from_repository(app_id, endpoint_id, repo_url, credentials.username, credentials.password)
        stack_containers = portainer_manager.wait_for_stack_containers(app_id, endpoint_id)
        if not stack_containers:
            raise CustomException(400, "Invalid Request", compose_manager._missing_stack_containers_error)

        if payload.domain:
            if forward_port is None:
                raise CustomException(400, "Invalid Request", "Cannot configure a domain because the compose file does not expose a target port.")
            add_installing_logs(install_tracking_id, "Configuring the domain", "")
            advanced_config_path = os.path.join(workspace_path, "src", "nginx-proxy.conf")
            if os.path.exists(advanced_config_path):
                advanced_config = FileHelper.read_file(advanced_config_path)
                ProxyManager().create_proxy_by_app([payload.domain], app_id, str(forward_port), advanced_config, "http")
            else:
                ProxyManager().create_proxy_by_app([payload.domain], app_id, str(forward_port), forward_scheme="http")

        add_installing_logs(install_tracking_id, "Installation complete", "")
        remove_app_installation(install_tracking_id)
    except CustomException as exc:
        modify_app_information(install_tracking_id, exc.details)
        remove_installation_logs(install_tracking_id)
        raise
    except Exception as exc:
        modify_app_information(install_tracking_id, "Compose installation failed")
        remove_installation_logs(install_tracking_id)
        logger.error(f"Compose installation failed for {app_id}: {exc}")
        raise CustomException()
    finally:
        if workspace_path and os.path.isdir(os.path.dirname(workspace_path)):
            shutil.rmtree(os.path.dirname(workspace_path), ignore_errors=True)