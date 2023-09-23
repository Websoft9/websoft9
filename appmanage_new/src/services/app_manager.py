
import json
import os
import shutil
from src.core.config import ConfigManager
from src.core.envHelper import EnvHelper
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.services.git_manager import GitManager
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.core.logger import logger
from src.services.proxy_manager import ProxyManager
from src.utils.file_manager import FileHelper
from src.utils.password_generator import PasswordGenerator


class AppManger:
    def install_app(self,appInstall: appInstall, endpointId: int = None):
        library_path = ConfigManager().get_value("docker_library", "path")
        portainerManager = PortainerManager()

        # if endpointId is None, get the local endpointId
        if endpointId is None:
            try:
                endpointId = portainerManager.get_local_endpoint_id()
            except (CustomException,Exception) as e:
                raise CustomException()
        else :
            # validate the endpointId is exists
            is_endpointId_exists = portainerManager.check_endpoint_exists(endpointId)

            if not is_endpointId_exists:
                raise CustomException(
                    status_code=404,
                    message="Invalid Request",
                    details="EndpointId Not Found"
                )
            
        # validate the app_name and app_version
        app_name = appInstall.app_name
        app_version = appInstall.edition.version
        self._check_appName_and_appVersion(app_name,app_version,library_path)

        # validate the app_id
        app_id = appInstall.app_id
        self._check_appId(app_id,endpointId)
     
        proxy_enabled = appInstall.proxy_enabled
        domain_names = appInstall.domain_names

        # validate the domain_names
        if proxy_enabled:
            self._check_domain_names(domain_names) 

        # Begin install app
        # Step 1 : create repo in gitea
        giteaManager = GiteaManager()
        repo_url =  giteaManager.create_repo(app_id)

        # Step 2 : initialize local git repo and push to gitea
        try:
            local_path = f"{library_path}/{app_name}"

            # The destination directory. 
            app_tmp_dir = "/tmp"
            app_tmp_dir_path = f"{app_tmp_dir}/{app_name}"

            # Check if the destination directory exists, create it if necessary.
            if not os.path.exists(app_tmp_dir):
                os.makedirs(app_tmp_dir)

            # If the specific target folder already exists, remove it before copying.
            if os.path.exists(app_tmp_dir_path):
                shutil.rmtree(app_tmp_dir_path)

            # Copy the entire directory.
            shutil.copytree(local_path, app_tmp_dir_path)

            # Modify the env file
            env_file_path = f"{app_tmp_dir_path}/.env"
            new_env_values = {
                "APP_NAME": app_id,
                "APP_VERSION": app_version,
                "POWER_PASSWORD": PasswordGenerator.generate_strong_password()
            }
            new_env_values["APP_URL"] = domain_names[0]
            EnvHelper(env_file_path).modify_env_values(new_env_values)

            # Get the forward port form env file
            forward_port = EnvHelper(env_file_path).get_env_value_by_key("APP_HTTP_PORT")

            # Commit and push to remote repo
            self._init_local_repo_and_push_to_remote(app_tmp_dir_path,repo_url)

            # Remove the tmp dir
            shutil.rmtree(app_tmp_dir_path)
        except (CustomException,Exception) as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            raise CustomException()
        
        # Step 3 : create stack in portainer
        try:
            user_name = ConfigManager().get_value("gitea","user_name")
            user_pwd = ConfigManager().get_value("gitea","user_pwd")
            portainerManager.create_stack_from_repository(app_id,endpointId,repo_url,user_name,user_pwd)
            stack_id = portainerManager.get_stack_by_name(app_id,endpointId)["Id"]
        except (CustomException,Exception) as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            raise CustomException()
        
        # Step 4 : create proxy in proxy
        try:            
            if domain_names:
                ProxyManager().create_proxy_for_app(domain_names,app_id,forward_port)
        except (CustomException,Exception) as e:
            # Rollback-1: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Rollback-2: remove stack in portainer
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            raise CustomException()


    def _check_appName_and_appVersion(self,app_name:str, app_version:str,library_path:str):
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

    def _check_appId(self,app_id:str,endpointId:int):
        """
        Check the app_id is exists in gitea and portainer

        Args:
            app_id (str): App Id
            endpointId (int): Endpoint Id

        Raises:
            CustomException: If the app_id is exists in gitea or portainer
        """
        # validate the app_id is exists in gitea
        giteaManager = GiteaManager()
        is_repo_exists = giteaManager.check_repo_exists(app_id)
        if is_repo_exists:
            logger.error(f"When install app,the app_id:{{app_id}} is exists in gitea")
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"App_id:{app_id} is exists in gitea"
            )
        
        # validate the app_id is exists in portainer
        portainerManager = PortainerManager()
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if is_stack_exists:
            logger.error(f"When install app, the app_id:{app_id} is exists in portainer")
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"app_id:{app_id} is exists in portainer"
            )
        
    def _check_domain_names(self,domain_names:list[str]):
        """
        Check the domain_names is exists in proxy

        Args:
            domain_names (list[str]): Domain Names

        Raises:
            CustomException: If the domain_names is not exists in proxy
        """
        ProxyManager().check_proxy_host_exists(domain_names)

    def _init_local_repo_and_push_to_remote(self,local_path:str,repo_url:str):
        """
        Initialize a local git repository from a directory and push to remote repo

        Args:
            local_path (str): The path to the local git repository.
            repo_url (str): The URL of the remote origin.
        """
        try:
            gitManager =GitManager(local_path) 
            gitManager.init_local_repo_from_dir()
            user_name = ConfigManager().get_value("gitea","user_name")
            user_pwd = ConfigManager().get_value("gitea","user_pwd")
            gitManager.push_local_repo_to_remote_repo(repo_url,user_name,user_pwd)
        except (CustomException,Exception) as e:
            logger.error(f"Init local repo and push to remote repo error:{e}")
            raise CustomException()
