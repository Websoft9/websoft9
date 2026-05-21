import os
import random
import shutil
import tempfile
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


def _load_compose_document(compose_content: str) -> dict:
    try:
        compose_document = yaml.safe_load(compose_content)
    except yaml.YAMLError as exc:
        raise CustomException(400, "Invalid Request", f"Compose syntax is invalid: {exc}")

    if not isinstance(compose_document, dict):
        raise CustomException(400, "Invalid Request", "Compose content must decode to an object.")

    services = compose_document.get("services")
    if not isinstance(services, dict) or not services:
        raise CustomException(400, "Invalid Request", "Compose content must define at least one service.")

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
    stack_id = None
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

        env_lines = [
            f"W9_ID={app_id}",
            f"W9_APP_NAME={payload.app_id}",
            "W9_DIST=compose",
            "W9_VERSION=custom",
        ]
        if payload.domain:
            env_lines.append(f"W9_URL={payload.domain}")
        for entry in payload.env:
            env_lines.append(f"{entry.key}={entry.value}")
        FileHelper.write_file(os.path.join(workspace_path, ".env"), "\n".join(env_lines) + "\n")

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
        stack_id = stack_info.get("Id")
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

        remove_app_installation(install_tracking_id)
        add_installing_logs(install_tracking_id, "Installation complete", "")
    except CustomException as exc:
        if repo_url:
            try:
                gitea_manager.remove_repo(app_id)
            except Exception:
                logger.warning(f"Failed to rollback compose repo {app_id}")
        if stack_id is not None:
            try:
                portainer_manager.remove_stack_and_volumes(stack_id, endpoint_id)
            except Exception:
                portainer_manager.remove_vloumes(app_id, endpoint_id)
        else:
            try:
                portainer_manager.remove_vloumes(app_id, endpoint_id)
            except Exception:
                logger.warning(f"Failed to rollback compose volumes for {app_id}")
        modify_app_information(install_tracking_id, exc.details)
        remove_installation_logs(install_tracking_id)
        raise
    except Exception as exc:
        if repo_url:
            try:
                gitea_manager.remove_repo(app_id)
            except Exception:
                logger.warning(f"Failed to rollback compose repo {app_id}")
        if stack_id is not None:
            try:
                portainer_manager.remove_stack_and_volumes(stack_id, endpoint_id)
            except Exception:
                portainer_manager.remove_vloumes(app_id, endpoint_id)
        else:
            try:
                portainer_manager.remove_vloumes(app_id, endpoint_id)
            except Exception:
                logger.warning(f"Failed to rollback compose volumes for {app_id}")
        modify_app_information(install_tracking_id, "Compose installation failed")
        remove_installation_logs(install_tracking_id)
        logger.error(f"Compose installation failed for {app_id}: {exc}")
        raise CustomException()
    finally:
        if workspace_path and os.path.isdir(os.path.dirname(workspace_path)):
            shutil.rmtree(os.path.dirname(workspace_path), ignore_errors=True)