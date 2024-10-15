import os
import json
from src.core.config import ConfigManager
from src.core.logger import logger
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.services.proxy_manager import ProxyManager
from src.services.app_status import appInstalling,appInstallingError

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

    # Get the max_apps from config
    max_apps = ConfigManager("system.ini").get_value("max_apps", "key")
    if max_apps:
        # Get all apps from the endpoint
        appInstallApps = AppManger().get_apps(endpointId)

        # Get the official and  status is 1(Active) or 3(Installing) apps
        app_official = [app for app in appInstallApps if app.app_official == True and (app.status == 1 or app.status == 3)]

        if len(app_official) >= int(max_apps):
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
    except CustomException as e:
        raise e
    except Exception as e:
        logger.error(f"When install app, validate appInstall error:{e}")
        raise CustomException()