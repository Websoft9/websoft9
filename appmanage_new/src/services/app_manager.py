import json
import os
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.core.logger import logger


class AppManger:
    def install_app(self,appInstall: appInstall, endpointId: int = None):
        portainerManager = PortainerManager()

        # if endpointId is None, get the local endpointId
        if endpointId is None:
            try:
                endpointId = portainerManager.get_local_endpoint_id()
            except CustomException:
                raise 
            except Exception:
                raise CustomException()
        else :
            # validate the endpointId is exists
            is_endpointId_exists = portainerManager.check_endpoint_exists(endpointId)

            if not is_endpointId_exists:
                raise CustomException(
                    status_code=404,
                    message="Not found",
                    details="EndpointId Not Found"
                )
            
        # validate the app_name and app_version
        app_name = appInstall.app_name
        app_version = appInstall.edition.version
        self._check_appName_and_appVersion(app_name,app_version)

        # validate the app_id
        app_id = appInstall.app_id
        self._check_appId(app_id,endpointId)

        # validate the domain_names
        
        
        



        



    def _check_appName_and_appVersion(self,app_name:str, app_version:str):
        """
        Check the app_name and app_version is exists in docker library

        Args:
            app_name (str): App Name
            app_version (str): App Version

        Raises:
            CustomException: If the app_name or app_version is not exists in docker library
        """
        library_path = ConfigManager().get_value("docker_library", "path")
        if not os.path.exists(f"{library_path}/{app_name}"):
            logger.error(f"When install app:{app_name}, the app is not exists in docker library")
            raise CustomException(
                status_code=400,
                message="App Name Not Supported",
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
                        message="App Version Not Supported",
                        details=f"app_version:{app_version} not supported",
                    )

    def _check_appId(self,app_id:str,endpointId:int):
        # validate the app_id is exists in gitea
        giteaManager = GiteaManager()
        is_repo_exists = giteaManager.check_repo_exists(app_id)
        if is_repo_exists:
            logger.error(f"When install app,the app_id:{{app_id}} is exists in gitea")
            raise CustomException(
                status_code=400,
                message="App_id Conflict",
                details=f"App_id:{app_id} Is Exists In Gitea"
            )
        
        # validate the app_id is exists in portainer
        portainerManager = PortainerManager()
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if is_stack_exists:
            logger.error(f"When install app, the app_id:{app_id} is exists in portainer")
            raise CustomException(
                status_code=400,
                message="App_id Conflict",
                details=f"app_id:{app_id} is exists in portainer"
            )