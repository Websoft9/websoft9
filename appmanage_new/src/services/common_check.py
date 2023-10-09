import os
import json
from src.core.logger import logger
from src.core.exception import CustomException
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.services.proxy_manager import ProxyManager

def check_appName_and_appVersion(app_name:str, app_version:str,library_path:str):
        """
        Check the app_name and app_version is exists in docker library

        Args:
            app_name (str): App Name
            app_version (str): App Version

        Raises:
            CustomException: If the app_name or app_version is not exists in docker library
        """
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

def check_appId(app_id:str,endpointId:int,giteaManager:GiteaManager,portainerManager:PortainerManager):
    """
    Check the app_id is exists in gitea and portainer

    Args:
        app_id (str): App Id
        endpointId (int): Endpoint Id

    Raises:
        CustomException: If the app_id is exists in gitea or portainer
    """
    # validate the app_id is exists in gitea
    is_repo_exists = giteaManager.check_repo_exists(app_id)
    if is_repo_exists:
        logger.error(f"When install app,the app_id:{{app_id}} is exists in gitea")
        raise CustomException(
            status_code=400,
            message="Invalid Request",
            details=f"App_id:{app_id} is exists in gitea"
        )
    
    # validate the app_id is exists in portainer
    is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
    if is_stack_exists:
        logger.error(f"When install app, the app_id:{app_id} is exists in portainer")
        raise CustomException(
            status_code=400,
            message="Invalid Request",
            details=f"app_id:{app_id} is exists in portainer"
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

def check_endpointId(endpointId, portainerManager):
    """
    Check the endpointId is exists

    Args:
        endpointId ([type]): [description]
        portainerManager ([type]): [description]

    Raises: 
        CustomException: If the endpointId is not exists
    """
    if endpointId is None:
        # Get the local endpointId
        endpointId = portainerManager.get_local_endpoint_id()       
    else :
        # validate the endpointId is exists
        is_endpointId_exists = portainerManager.check_endpoint_exists(endpointId)
        if not is_endpointId_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="EndpointId Not Found"
            )
    return endpointId