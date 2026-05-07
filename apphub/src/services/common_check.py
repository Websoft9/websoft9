import os
import json
import docker
from src.core.config import ConfigManager
from src.core.logger import logger
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.services.proxy_manager import ProxyManager
from src.services.app_status import appInstalling,appInstallingError
from src.services.product_metadata import read_product_edition


def _get_host_bound_ports() -> set:
    """
    Return the set of TCP host ports currently bound by all running containers.
    Uses the Docker socket so results reflect the real host-level port bindings.
    """
    bound = set()
    try:
        client = docker.from_env()
        for container in client.containers.list():
            ports = (container.attrs.get('NetworkSettings') or {}).get('Ports') or {}
            for binding_list in ports.values():
                if not binding_list:
                    continue
                for binding in binding_list:
                    host_port = binding.get('HostPort')
                    if host_port:
                        try:
                            bound.add(int(host_port))
                        except ValueError:
                            pass
    except Exception as e:
        logger.warning(f"Could not scan Docker container ports for conflict check: {e}")
    return bound


def _read_template_ports(app_name: str) -> set:
    """
    Read W9_*PORT_SET values from the app template's .env file.
    Returns the set of integer port numbers found.
    """
    ports = set()
    try:
        library_path = ConfigManager("system.ini").get_value("docker_library", "path")
        env_path = os.path.join(library_path, app_name, ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    if 'PORT_SET' in key:
                        try:
                            ports.add(int(val.strip()))
                        except ValueError:
                            pass
    except Exception as e:
        logger.warning(f"Could not read template .env for port check ({app_name}): {e}")
    return ports


def check_port_conflicts(settings: dict, app_name: str = None):
    """
    Check whether any port requested (from settings overrides and/or the app template)
    is already in use — either bound by a running Docker container or claimed by an
    app that is currently being installed.

    Args:
        settings (dict): The settings dict from appInstall (may be None).
        app_name (str): App name used to read template .env default ports (optional).
    Raises:
        CustomException: If a requested port is already in use.
    """
    # Collect ports explicitly requested via settings
    settings_ports: dict[str, int] = {}
    if settings:
        for key, val in settings.items():
            if 'PORT_SET' in key:
                try:
                    settings_ports[key] = int(val)
                except (ValueError, TypeError):
                    pass

    # Also collect template default ports not already overridden by settings
    template_ports: dict[str, int] = {}
    if app_name:
        override_values = set(settings_ports.values())
        for port in _read_template_ports(app_name):
            if port not in override_values:
                template_ports[f'W9_PORT_DEFAULT_{port}'] = port

    requested = {**settings_ports, **template_ports}
    if not requested:
        return

    # Ports claimed by apps currently being installed (not yet Docker-bound)
    installing_ports: set = set()
    for entry in appInstalling.values():
        installing_ports.update(entry.get('reserved_ports') or set())

    docker_ports = _get_host_bound_ports()
    all_used = docker_ports | installing_ports

    for key, port in requested.items():
        if port in all_used:
            source = 'a running container' if port in docker_ports else 'an app currently being installed'
            logger.error(f"Port conflict: {port} is already claimed by {source}")
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"Port {port} is already in use. Please choose a different port.",
            )

def check_appName_and_appVersion(app_name:str, app_version:str):
        """
        Check the app_name and app_version is exists in docker library

        Args:
            app_name (str): App Name
            app_version (str): App Version
        Raises:
            CustomException: If the app_name or app_version is not exists in docker library
        """
        try:
            # Get docker library path
            library_path = ConfigManager("system.ini").get_value("docker_library", "path")

            if not os.path.exists(f"{library_path}/{app_name}"):
                logger.error(f"When install app:{app_name}, the app is not exists in docker library")
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"app_name:{app_name} not supported",
                )
            else:
                with open(f"{library_path}/{app_name}/variables.json", "r") as f:
                    variables = json.load(f)
                    community_editions = [d for d in variables["edition"] if d["dist"] == "community"]
                    if not any(
                        app_version in d["version"] for d in community_editions
                    ):
                        logger.error(f"When install app:{app_name}, the app version:{app_version} is not exists in docker library")
                        raise CustomException(
                            status_code=400,
                            message="Invalid Request",
                            details=f"app_version:{app_version} not supported",
                        )
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"When install app:{app_name}, validate app_name and app_version error:{e}")
            raise CustomException()

def check_appId(app_id:str,endpointId:int,giteaManager:GiteaManager,portainerManager:PortainerManager):
    """
    Check the app_id is exists in gitea and portainer

    Args:
        app_id (str): App Id
        endpointId (int): Endpoint Id

    Raises:
        CustomException: If the app_id is exists in gitea or portainer
    """

    # validate the app_id is installing
    for app_uuid,app in appInstalling.items():
        if app_id == app.get("app_id", None):
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is installing"
            )
        
    # validate the app_id is installing error
    for app_uuid,app in appInstallingError.items():
        if app_id == app.get("app_id", None):
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"The app with the same name has already failed to install. Please check in 'My Apps'."
            )

    # validate the app_id is exists in gitea
    is_repo_exists = giteaManager.check_repo_exists(app_id)
    if is_repo_exists:
        logger.error(f"When install app,the app_id:{app_id} is exists in gitea")
        raise CustomException(
            status_code=400,
            message="Invalid Request",
            details=f"App_id:{app_id} is exists(in gitea)"
        )
    
    # validate the app_id is exists in portainer
    is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
    if is_stack_exists:
        logger.error(f"When install app, the app_id:{app_id} is exists in portainer")
        raise CustomException(
            status_code=400,
            message="Invalid Request",
            details=f"app_id:{app_id} is exists(in portainer)"
        )

def check_domain_names(domain_names:list[str]):
    """
    Check the domain_names is exists in proxy

    Args:
        domain_names (list[str]): Domain Names

    Raises:
        CustomException: If the domain_names is not exists in proxy
    """
    ProxyManager().check_proxy_host_exists(domain_names)

def check_endpointId(endpointId:int, portainerManager):
    """
    Check the endpointId is exists

    Args:
        endpointId (int): Endpoint Id
        portainerManager (PortainerManager): Portainer Manager

    Raises: 
        CustomException: If the endpointId is not exists
    """
    # validate the endpointId is exists
    if endpointId:
        is_endpointId_exists = portainerManager.check_endpoint_exists(endpointId)
        if not is_endpointId_exists:
            logger.error(f"EndpointId:{endpointId} Not Found")
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="EndpointId Not Found"
            )

def check_apps_number(endpointId:int):
    """
    Check the apps number is exceed the maximum number of apps

    Args:
        endpointId (int): Endpoint Id
    """
    # 在这里导入是为避免和app_manager的循环导入，导致代码报错
    from src.services.app_manager import AppManger

    edition = read_product_edition()
    max_apps = edition.max_apps
    if max_apps is not None:
        # Get all apps from the endpoint
        appInstallApps = AppManger().get_apps(endpointId)

        # Get the official and  status is 1(Active) or 3(Installing) apps
        app_official = [app for app in appInstallApps if app.app_official == True and (app.status == 1 or app.status == 3)]

        if len(app_official) >= max_apps:
            logger.error(f"Exceed the maximum number of apps")
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Exceed the maximum number of apps"
            )

def install_validate(appInstall:appInstall,endpointId:int):
    """
    before install app, check the appInstall is valid

    Args:
        appInstall (appInstall): App Install
    Raises:
        CustomException: If the appInstall is not valid
    """
    try:
        portainerManager = PortainerManager()
        giteaManager = GiteaManager()

        # Get the app_name and app_version
        app_name = appInstall.app_name
        app_version = appInstall.edition.version

        proxy_enabled = appInstall.proxy_enabled
        domain_names = appInstall.domain_names
        app_id = appInstall.app_id

        # Check the app_name and app_version is exists in docker library
        check_appName_and_appVersion(app_name, app_version)

        # Check the app_id is exists in gitea and portainer
        check_appId(app_id, endpointId, giteaManager, portainerManager)

        # Check the domain_names is exists in proxy
        if proxy_enabled:
            check_domain_names(domain_names)

        # Check the endpointId is exists
        check_endpointId(endpointId, portainerManager)

        # Check the apps number is exceed the maximum number of apps
        check_apps_number(endpointId)

        # Check port conflicts for any W9_*PORT_SET settings (includes template defaults)
        check_port_conflicts(appInstall.settings, app_name)
    except CustomException as e:
        raise e
    except Exception as e:
        logger.error(f"When install app, validate appInstall error:{e}")
        raise CustomException()