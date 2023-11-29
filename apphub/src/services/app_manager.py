import base64
import json
import os
import shutil
import random
from datetime import datetime
from src.core.config import ConfigManager
from src.core.envHelper import EnvHelper
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.schemas.appResponse import AppResponse
from src.services.common_check import check_endpointId
from src.services.git_manager import GitManager
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.core.logger import logger
from src.services.proxy_manager import ProxyManager
from src.utils.file_manager import FileHelper
from src.utils.password_generator import PasswordGenerator
from src.services.app_status import appInstalling, appInstallingError,start_app_installation,remove_app_installation,modify_app_information,remove_app_from_errors_by_app_id

class AppManger:
    def get_catalog_apps(self,locale:str):
        """
        Get catalog apps

        Args:
            locale (str): The language to get catalog apps from.
        """
        try:
            # Get the app media path
            base_path = ConfigManager("system.ini").get_value("app_media", "path")
            app_media_path = base_path + 'catalog_' + locale + '.json'
            # check the app media path is exists
            if not os.path.exists(app_media_path):
                logger.error(f"Get app'catalog error: {app_media_path} is not exists")
                raise CustomException()
            
            # Get the app catalog list
            with open(app_media_path, "r") as f:
                data = json.load(f)
                return data
        except (CustomException,Exception) as e:
            logger.error(f"Get app'catalog error:{e}")
            raise CustomException()

    def get_available_apps(self, locale:str):
        """
        Get available apps

        Args:
            locale (str): The language to get available apps from.
        """
        try:
            # Get the app media path
            base_path = ConfigManager("system.ini").get_value("app_media", "path")
            app_media_path = base_path + 'product_' + locale + '.json'
            # check the app media path is exists
            if not os.path.exists(app_media_path):
                logger.error(f"Get available apps error: {app_media_path} is not exists")
                raise CustomException()
            
            # Get the app available list
            with open(app_media_path, "r",encoding='utf-8') as f:
                data = json.load(f)
            
            # Iterate over the keys in data
            app_lib_path = ConfigManager("system.ini").get_value("docker_library", "path")
            for item in data:
                key = item.get("key")
                env_path =app_lib_path+ f"/{key}/.env"
                if os.path.exists(env_path):
                    env_helper = EnvHelper(env_path)
                    env_data = env_helper.get_all_values()
                    settings = {k: v for k, v in env_data.items() if k.startswith("W9_") and k.endswith("_SET")}
                    item["settings"] = settings
                    item["is_web_app"] = "W9_URL" in env_data
                            
            return data
        except (CustomException,Exception) as e:
            logger.error(f"Get available apps error:{e}")
            raise CustomException()

    def get_apps(self,endpointId:int = None):
        """
        Get apps

        Args:
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        # Get the portainer manager
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
            check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        try:
            # Set the apps info for response
            apps_info = []
            # Get the stacks by endpointId from portainer
            stacks = portainerManager.get_stacks(endpointId)
            for stack in stacks:
                stack_name = stack.get("Name",None)
                if stack_name is not None:
                    # Get the app info by stack_name from portainer
                    app_info = self.get_app_by_id(stack_name,endpointId)
                    apps_info.append(app_info)

            # Get the not stacks(not installed apps)
            all_containers = portainerManager.get_containers(endpointId) # Get all containers by endpointId from portainer

            # Set the not stacks info for response(app not install by portainer)
            not_stacks = [] 
            for container in all_containers:
                # Get the container labels
                container_labels = container.get("Labels",None)
                if container_labels is not None:
                    # Get the container_project
                    container_project = container_labels.get("com.docker.compose.project",None)
                    if container_project is not None:
                        # Check the container_project is exists in stacks
                        if not any(container_project in stack.get("Name",[]) for stack in stacks):
                            # Add the not stacks
                            not_stacks.append(container_project)
            
            # Remove the duplicate elements
            not_stacks = list(set(not_stacks))

            # Remove the websoft9
            if "websoft9" in not_stacks:
                not_stacks.remove("websoft9")
            
            # Set the not_stacks info to apps_info
            for not_stack in not_stacks:
                not_stack_response = AppResponse(
                    app_id = not_stack,
                    app_official = False,
                )
                apps_info.append(not_stack_response)

            # Get the installing apps(if app is in installing and in stasks or not_stacks,remove it)
            for app_uuid,app in appInstalling.items(): 
                app_response = AppResponse(
                        app_id = app.get("app_id", None),
                        status = app.get("status", None),
                        app_name = app.get("app_name", None),
                        app_official = app.get("app_official", None),
                        error = app.get("error", None),
                    )
                if app_response.app_id in not_stacks:
                    # If app_id is in not_stacks, remove the corresponding AppResponse from apps_info
                    apps_info = [app_info for app_info in apps_info if app_info.app_id != app_response.app_id]
                if any(app_info.app_id == app_response.app_id for app_info in apps_info):
                    #从apps_info中删除app_id对应的AppResponse
                    apps_info = [app_info for app_info in apps_info if app_info.app_id != app_response.app_id]
                apps_info.append(app_response)

            # Get the installing error apps
            for app_uuid,app in list(appInstallingError.items()):
                app_response = AppResponse(
                        app_id = app.get("app_id", None),
                        status = app.get("status", None),
                        app_name = app.get("app_name", None),
                        app_official = app.get("app_official", None),
                        error = app.get("error", None),
                    )
                apps_info.append(app_response)

            return apps_info
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Get apps error:{e}")
            raise CustomException()

    def get_app_by_id(self,app_id:str,endpointId:int = None):
        """
        Get app by app_id

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        
        # Get stack_info by app_id from portainer
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        # Get the stack_id
        stack_id = stack_info.get("Id",None)
        # Check the stack_id is exists
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get the stack_status
        stack_status = stack_info.get("Status",0)
        # Get the gitConfig
        gitConfig = stack_info.get("GitConfig",{}) or {}
        # Get the creationDate
        creationDate = stack_info.get("CreationDate","")
        # Get the domain_names by app_id from nginx proxy manager
        domain_names = ProxyManager().get_proxy_host_by_app(app_id)
        # Set the proxy_enabled
        if not domain_names:
            proxy_enabled = False
        else :
            proxy_enabled = True
        # Get the volumes by app_id from portainer
        app_volumes = portainerManager.get_volumes_by_stack_name(app_id,endpointId,False)

        # if stack is empty(status=2-inactive),can not get it
        if stack_status == 1:
            # Get the containers by app_id from portainer
            app_containers = portainerManager.get_containers_by_stack_name(app_id,endpointId)
            
            # Get the main container
            main_container_id = None
            app_env = []
            app_env_format = {} # format app_env to dict
            for container in app_containers:
                if f"/{app_id}" in container.get("Names", []):
                    main_container_id = container.get("Id", "")
                    break
            if main_container_id:
                # Get the main container info by main_container_id from portainer
                main_container_info =  portainerManager.get_container_by_id(endpointId, main_container_id)
                # Get the env from main_container_info
                app_env = main_container_info.get("Config", {}).get("Env", [])
                
            # Get info from app_env
            app_name = None
            app_dist = None
            app_version = None
            w9_url = None
            w9_url_replace = False
            for item in app_env:
                key, value = item.split("=", 1)
                app_env_format[key] = value
                if key == "W9_APP_NAME":
                    app_name = value
                elif key == "W9_DIST":
                    app_dist = value
                elif key == "W9_VERSION":
                    app_version = value
                elif key == "W9_URL_REPLACE":
                    w9_url_replace = value
                elif key == "W9_URL":
                    w9_url = value

            for domain in domain_names:
                domain["w9_url_replace"] = w9_url_replace
                domain["w9_url"] = w9_url
            
            # Set the appResponse
            appResponse = AppResponse(
                app_id = app_id,
                endpointId = endpointId,
                app_name = app_name,
                app_dist = app_dist,
                app_version = app_version,
                app_official = True,
                proxy_enabled = proxy_enabled,
                domain_names = domain_names,
                status = stack_status,
                creationDate = creationDate,
                gitConfig = gitConfig,
                containers = app_containers,
                volumes = app_volumes,
                env = app_env_format
            )
            return appResponse
        else:
            appResponse = AppResponse(
                app_id = app_id,
                endpointId = endpointId,
                app_name = "",
                app_dist = "",
                app_version = "",
                app_official = True,
                proxy_enabled = proxy_enabled,
                domain_names = domain_names,
                status = stack_status,
                creationDate = creationDate,
                gitConfig = gitConfig,
                containers = [],
                volumes = app_volumes,
                env = {}
            )
            return appResponse
    
    def install_app(self,appInstall: appInstall, endpointId: int = None):
        """
        Install app

        Args:
            appInstall (appInstall): The app install info.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        # Get the portainer and gitea manager
        portainerManager = PortainerManager()
        giteaManager = GiteaManager()

        # Get the info from appInstall
        app_name = appInstall.app_name
        app_version = appInstall.edition.version
        app_id = appInstall.app_id
        proxy_enabled = appInstall.proxy_enabled
        domain_names = appInstall.domain_names
        settings = appInstall.settings

        # Check the endpointId is exists.
        if endpointId is None:
            # Get the local endpointId
            endpointId = portainerManager.get_local_endpoint_id()

        # generate app_id
        app_id = app_id + "_" + PasswordGenerator.generate_random_string(5)
        
        # add app to appInstalling
        app_uuid = start_app_installation(app_id, app_name)

        # Install app - Step 1 : create repo in gitea
        try:
            repo_url =  giteaManager.create_repo(app_id)
        except CustomException as e:
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            raise
        except Exception as e:
            # modify app status: error
            modify_app_information(app_uuid,"Create repo error")
            logger.error(f"Create repo error:{e}")
            raise CustomException()

        # Install app - Step 2 : initialize local git repo and push to gitea
        try:
            # The source directory.
            library_path = ConfigManager("system.ini").get_value("docker_library", "path")
            local_path = f"{library_path}/{app_name}"

            # Create a temporary directory.
            app_tmp_dir = "/tmp"
            # Get system time
            now = datetime.now()
            # Convert the time to a string
            timestamp_str = now.strftime("%Y%m%d%H%M%S%f")
            # Generate a random number
            rand_num = random.randint(1000, 9999)

            # 将时间戳和随机数添加到 app_name 后面
            app_tmp_dir_path = f"{app_tmp_dir}/{app_name}_{timestamp_str}_{rand_num}"

            # If the temporary directory does not exist, create it.
            if not os.path.exists(app_tmp_dir):
                os.makedirs(app_tmp_dir)

            # If the specific target folder already exists, remove it before copying.
            if os.path.exists(app_tmp_dir_path):
                shutil.rmtree(app_tmp_dir_path)

            # Copy the entire directory.
            shutil.copytree(local_path, app_tmp_dir_path)

            # Modify the env file
            env_file_path = f"{app_tmp_dir_path}/.env"
            envHelper = EnvHelper(env_file_path)

            # Set the install info to env file
            envHelper.set_value("W9_APP_NAME", app_name)
            envHelper.set_value("W9_ID", app_id)
            envHelper.set_value("W9_DIST", "community")
            envHelper.set_value("W9_VERSION", app_version)
            envHelper.set_value("W9_POWER_PASSWORD", PasswordGenerator.generate_strong_password())

            # Get "W9_URL" from env file (validate the app is web app)
            is_web_app = envHelper.get_value("W9_URL")
            if is_web_app:
                envHelper.set_value("W9_URL", domain_names[0])
                # validate is bind ip(proxy_enabled is false)
                # if not proxy_enabled:
                #     envHelper.set_value("W9_URL", domain_names[0])
                # else:
                #     replace_domain_name = domain_names[0]
                #     replace_domain_name = replace_domain_name.replace(replace_domain_name.split(".")[0], app_id, 1)
                #     domain_names[0] = replace_domain_name
                #     envHelper.set_value("W9_URL", domain_names[0])

            # Set the settings to env file
            if settings:
                for key, value in settings.items():
                    envHelper.set_value(key, value)
           
            # Commit and push to remote repo
            self._init_local_repo_and_push_to_remote(app_tmp_dir_path,repo_url)
        except CustomException as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            raise
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid,"Initialize repo error")
            logger.error(f"Initialize repo error:{e}")
            raise CustomException()
        
        # Install app - Step 3 : create stack in portainer
        try:
            # Get gitea user_name and user_pwd
            user_name = ConfigManager().get_value("gitea","user_name")
            user_pwd = ConfigManager().get_value("gitea","user_pwd")

            # Create stack in portainer
            stack_info = portainerManager.create_stack_from_repository(app_id,endpointId,repo_url,user_name,user_pwd)

            # Get the stack_id
            stack_id = stack_info.get("Id")
        except CustomException as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Remove volumes
            portainerManager.remove_vloumes(app_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            raise
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Remove volumes
            portainerManager.remove_vloumes(app_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,"Create stack error")
            logger.error(f"Create stack error:{e}")
            raise CustomException()
        
        # Install app - Step 4 : create proxy in nginx proxy manager
        try:
            # check the app is web app
            if is_web_app:
                if proxy_enabled and domain_names:
                    # Get the forward port form env file
                    http_port = EnvHelper(env_file_path).get_value("W9_HTTP_PORT")
                    https_port = EnvHelper(env_file_path).get_value("W9_HTTPS_PORT")

                    if http_port:
                        forward_scheme = "http"
                        forward_port = http_port
                    elif https_port:
                        forward_scheme = "https"
                        forward_port = https_port
                    
                    # Get the nginx proxy config path
                    nginx_proxy_path = f"{app_tmp_dir_path}/src/nginx-proxy.conf"
                    if os.path.exists(nginx_proxy_path):
                        # Get the advanced config
                        advanced_config = FileHelper.read_file(nginx_proxy_path)
                        # Create proxy in nginx proxy manager
                        ProxyManager().create_proxy_by_app(domain_names,app_id,forward_port,advanced_config,forward_scheme)
                    else:
                        # Create proxy in nginx proxy manager
                        ProxyManager().create_proxy_by_app(domain_names,app_id,forward_port,forward_scheme=forward_scheme)
        except CustomException as e:
            # Rollback-1: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Rollback-2: remove stack in portainer
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            raise
        except Exception as e:
            # Rollback-1: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Rollback-2: remove stack in portainer
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,"Create proxy error")
            logger.error(f"Create proxy error:{e}")
            raise CustomException()

        # remove app from installing
        remove_app_installation(app_uuid)

        # Remove the tmp dir
        shutil.rmtree(app_tmp_dir_path)

        logger.access(f"Successfully installed app: [{app_id}] and created domains:{domain_names}")
        # return result

    def redeploy_app(self,app_id:str,pull_image:bool,endpointId:int = None):
        """
        Redeploy app

        Args:
            app_id (str): The app id.
            pull_image (bool): Whether to pull the image when redeploying the app.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_id
        stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        else:
            user_name = ConfigManager().get_value("gitea","user_name")
            user_pwd = ConfigManager().get_value("gitea","user_pwd")
            # redeploy stack
            portainerManager.redeploy_stack(stack_id,endpointId,pull_image,user_name,user_pwd)
            logger.access(f"Successfully redeployed app: [{app_id}]")

    def uninstall_app(self,app_id:str,purge_data:bool,endpointId:int = None):
        """
        Uninstall app

        Args:
            app_id (str): The app id.
            purge_data (bool): Whether to purge data when uninstalling the app.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_id
        stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        
        # get stack status,if stack is empty(status=2-inactive),can not uninstall it
        stack_status = portainerManager.get_stack_by_name(app_id,endpointId).get("Status")
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not uninstall it,you can remove it"
            )
        
        if purge_data:
            # Uninstall app - Step 1 : remove proxy in nginx proxy manager
            # Check the proxy is exists
            proxyManager = ProxyManager()
            # Check the proxy is exists
            proxys_host = proxyManager.get_proxy_host_by_app(app_id)
            # If the proxy is exists, remove it
            if proxys_host:
                # Remove proxy
                proxyManager.remove_proxy_host_by_app(app_id)

            # Uninstall app - Step 2 : remove repo in gitea
            # Check the repo is exists
            giteaManager = GiteaManager()
            is_repo_exists = giteaManager.check_repo_exists(app_id)
            if is_repo_exists:
                # Remove repo
                giteaManager.remove_repo(app_id)
            
            # Uninstall app - Step 3 : remove stack in portainer
            # Get stack_id by app_id from portainer
            stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
            if stack_id is None:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"{app_id} Not Found"
                )
            # remove stack and volumes
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            logger.access(f"Successfully uninstalled app: [{app_id}] and removed all data")
        else:
            # down stack
            portainerManager.down_stack(stack_id,endpointId)
            logger.access(f"Successfully uninstalled app: [{app_id}] and keep data")

    def remove_app(self,app_id:str,endpointId:int = None):
        """
        Remove app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_id
        stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # get stack status,if stack is not empty(status=1-active),can not remove it
        stack_status = portainerManager.get_stack_by_name(app_id,endpointId).get("Status")
        if stack_status == 1:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is not inactive, please uninstall it first"
            )
        # Check the proxy is exists
        proxyManager = ProxyManager()
        proxys_host = proxyManager.get_proxy_host_by_app(app_id)
        # If the proxy is exists, remove it
        if proxys_host:
            proxyManager.remove_proxy_host_by_app(app_id)

        # Check the repo is exists
        giteaManager = GiteaManager()
        is_repo_exists = giteaManager.check_repo_exists(app_id)
        if is_repo_exists:
            giteaManager.remove_repo(app_id)
        # remove stack and volumes
        portainerManager.remove_stack_and_volumes(stack_id,endpointId)

        logger.access(f"Successfully removed app: [{app_id}]")

    def remove_error_app(self,app_id:str):
        """
        Remove error app

        Args:
            app_id (str): The error app id.
        """
        # validate the app_id is exists in appInstallingError
        try:
            is_app_in_appInstallingError = any(item['app_id'] == app_id for item in appInstallingError.values())
            if not is_app_in_appInstallingError:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Error App:{app_id}  Not Found"
                )
            # remove app from appInstallingError
            remove_app_from_errors_by_app_id(app_id)
        except CustomException as e:
            raise
        except Exception as e:
            logger.error(f"Remove error app error:{e}")
            raise CustomException()    

        logger.access(f"Successfully removed error app: [{app_id}]")

    def start_app(self,app_id:str,endpointId:int = None):
        """
        Start app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_info by app_id from portainer
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # validate the stack is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not start it,you can redeploy it"
            )
        # start stack
        portainerManager.start_stack(app_id,endpointId)
        logger.access(f"Successfully started app: [{app_id}]")

    def stop_app(self,app_id:str,endpointId:int = None):
        """
        Stop app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.  
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_info by app_id from portainer
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # validate the stack is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not stop it,you can redeploy it"
            )
        # stop stack
        portainerManager.stop_stack(app_id,endpointId)
        logger.access(f"Successfully stopped app: [{app_id}]")

    def restart_app(self,app_id:str,endpointId:int = None):
        """
        Restart app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_info by app_id from portainer
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # validate the stack is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not restart it,you can redeploy it"
            )
        # restart stack
        portainerManager.restart_stack(app_id,endpointId)
        logger.access(f"Successfully restarted app: [{app_id}]")
        
    def get_proxys_by_app(self,app_id:str,endpointId:int = None):
        """
        Get proxys by app_id

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        proxyManager = ProxyManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # Check the app_id is exists
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get the proxys
        return proxyManager.get_proxy_host_by_app(app_id)

    def create_proxy_by_app(self,app_id:str,domain_names:list[str],endpointId:int = None):
        """
        Create proxy by app_id

        Args:
            app_id (str): The app id.
            domain_names (list[str]): The domain names.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # Check the app_id is exists
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Check the app is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not create proxy,you can redeploy it"
            )
        
        # Check the domain_names is exists
        # check_domain_names(domain_names)

        # Get the forward port
        stack_env = self.get_app_by_id(app_id,endpointId).env
        if stack_env:
            # Get the forward_port
            http_port = stack_env.get("W9_HTTP_PORT",None)
            https_port = stack_env.get("W9_HTTPS_PORT",None)
            if http_port:
                forward_scheme = "http"
                forward_port = http_port
            elif https_port:
                forward_scheme = "https"
                forward_port = https_port
            # Create proxy
            if forward_port:
                w9_url = stack_env.get("W9_URL",None)
                w9_url_replace = stack_env.get("W9_URL_REPLACE",None)

                if w9_url and w9_url_replace:
                    # Get the all proxys by app_id
                    all_domain_names = proxyManager.get_proxy_host_by_app(app_id)
                    # if all_domain_names is empty,create proxy
                    if not all_domain_names:
                        # update the env file
                            self._update_gitea_env_file(app_id,w9_url,domain_names[0])           
                            # redeploy app
                            self.redeploy_app(app_id,False)
                    else:
                        combined_domain_names = []
                        for item in all_domain_names:
                            combined_domain_names.extend(item['domain_names'])
                        combined_domain_names.extend(domain_names)

                        if w9_url not in combined_domain_names:
                            # update the env file
                            self._update_gitea_env_file(app_id,w9_url,domain_names[0])           
                            # redeploy app
                            self.redeploy_app(app_id,False)

                # Get the forward scheme form env file: http or https
                proxy_host = proxyManager.create_proxy_by_app(domain_names,app_id,forward_port,forward_scheme=forward_scheme)
                if proxy_host:
                    logger.access(f"Successfully created domains:{domain_names} for app: [{app_id}]")
                    return proxy_host
                else:
                    logger.error(f"Create app:{app_id} proxy error")
                    raise CustomException()
            else:
                logger.error(f"Get app:{app_id} forward_port error")
                raise CustomException()
        else:
            logger.error(f"Get app:{app_id} env error")
            raise CustomException()

    def remove_proxy_by_app(self,app_id:str,endpointId:int = None):
        """
        Remove proxy by app_id

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # Check the app_id is exists
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        #  Get the domain_names by app_id from nginx proxy manager
        host = proxyManager.get_proxy_host_by_app(app_id)
        if not host:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is not exists proxy"
            )

        # Remove proxy
        proxyManager.remove_proxy_host_by_app(app_id)
        logger.access(f"Successfully removed all domains for app: [{app_id}]")

    def remove_proxy_by_id(self,proxy_id:int,client_host:str):
        """
        Remove proxy by proxy_id

        Args:
            proxy_id (int): The proxy id.
        """
        # Check the proxy id is exists
        try:
            proxyManager = ProxyManager()
            host = proxyManager.get_proxy_host_by_id(proxy_id)
            if host is None:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Proxy ID:{proxy_id} Not Found"
                )
            # Get the app_id by proxy_id
            app_id = host.get("forward_host",None)
            if app_id:
                # Get the app_info by app_id 
                app_info = self.get_app_by_id(app_id)
                if app_info:
                    # Get the w9_url and w9_url_replace
                    w9_url_replace = next((element.get("w9_url_replace") for element in app_info.domain_names if element.get("id") == proxy_id), None)
                    w9_url = next((element.get("w9_url") for element in app_info.domain_names if element.get("id") == proxy_id), None)
                    
                    # validate w9_url_replace is true
                    if w9_url_replace:
                        domain_names = host.get("domain_names",None)
                        if domain_names:
                            # Get the all proxys by app_id
                            app_proxys =  self.get_proxys_by_app(app_id)
                            # if w9_url is in domain_names：
                            if w9_url in domain_names:
                                new_w9_url = None
                                if len(app_proxys) == 1 and app_proxys[0].get("id") == proxy_id:
                                    new_w9_url = client_host
                                elif len(app_proxys) > 1:
                                    # Get the first proxy_host
                                    proxy_host = next((proxy for proxy in app_proxys if proxy.get("id") != proxy_id), None)
                                    if proxy_host:
                                        # Get the domain_names
                                        domain_names = proxy_host.get("domain_names",None)
                                        if domain_names:
                                            # Get the first domain_name
                                            new_w9_url = domain_names[0]
                                
                                # update the env file
                                self._update_gitea_env_file(app_id,w9_url,new_w9_url)

                                # redeploy app
                                self.redeploy_app(app_id,False)
                    # Remove proxy
                    proxyManager.remove_proxy_host_by_id(proxy_id)
                    logger.access(f"Successfully removed domains:{host['domain_names']} for app: [{app_id}]")
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Remove proxy error:{e}")
            raise CustomException()

    def update_proxy_by_app(self,proxy_id:str,domain_names:list[str],endpointId:int = None):
        """
        Update proxy by app_id

        Args:
            proxy_id (str): The proxy id.
            domain_names (list[str]): The domain names.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # Check the proxy id is exists
        host = proxyManager.get_proxy_host_by_id(proxy_id)
        if host is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"Proxy ID:{proxy_id} Not Found"
            )
        
        # Get the app_id by proxy_id
        app_id = host.get("forward_host",None)
        old_domain_names = host.get("domain_names",None)
        logger.access(f"old_domain_names:{old_domain_names}")
        if app_id:
            # Get the app_info by app_id 
            app_info = self.get_app_by_id(app_id)
            if app_info:
                # Get the w9_url and w9_url_replace
                w9_url_replace = next((element.get("w9_url_replace") for element in app_info.domain_names if element.get("id") == proxy_id), None)
                w9_url = next((element.get("w9_url") for element in app_info.domain_names if element.get("id") == proxy_id), None)
                
                # validate w9_url_replace is true
                if w9_url_replace and w9_url:
                    if w9_url in old_domain_names:
                        if w9_url not in domain_names:
                            # update the env file
                            self._update_gitea_env_file(app_id,w9_url,domain_names[0])
                            # redeploy app
                            self.redeploy_app(app_id,False)

        # Update proxy
        result = proxyManager.update_proxy_by_app(proxy_id,domain_names)
        logger.access(f"Successfully updated domains:{domain_names} for app: [{host['forward_host']}]")
        return result

    def _init_local_repo_and_push_to_remote(self,local_path:str,repo_url:str):
        """
        Initialize a local git repository from a directory and push to remote repo

        Args:
            local_path (str): The path to the local git repository.
            repo_url (str): The URL of the remote origin.
        """
        try:
            # instantiate a GitManager object
            gitManager =GitManager(local_path) 

            # Initialize a local git repository from a directory
            gitManager.init_local_repo_from_dir()

            user_name = ConfigManager().get_value("gitea","user_name")
            user_pwd = ConfigManager().get_value("gitea","user_pwd")

            # Push the local repo to remote repo
            gitManager.push_local_repo_to_remote_repo(repo_url,user_name,user_pwd)
        except (CustomException,Exception) as e:
            logger.error(f"Init local repo and push to remote repo error:{e}")
            raise CustomException()

    def _update_gitea_env_file(self,app_id:str,key:str,value:str):
        """
        Update the env file w9_url

        Args:
            app_id (str): The app id.
            domain_name (str): The domain name.
        """
        try:
            giteaManager = GiteaManager()
            # Get the env file from git repo
            git_env_file = giteaManager.get_file_content_from_repo(app_id,".env")
            # Get the env file sha
            git_env_file_sha = git_env_file.get("sha",None)
            # Get the env file content
            git_env_file_content = git_env_file.get("content",None)
            if git_env_file_sha and git_env_file_content:
                # Get the env file content
                env_file_content = base64.b64decode(git_env_file_content).decode("utf-8")
                # Modify the env file content
                env_file_content = env_file_content.replace(key,value)
                # base64 encode for env_file_content
                env_file_content = base64.b64encode(env_file_content.encode("utf-8")).decode("utf-8")
                # Update the env file to git repo
                giteaManager.update_file_in_repo(app_id,".env",env_file_content,git_env_file_sha)
                logger.access(f"Update the git repo env file for app: [{app_id}]")
            else:
                logger.error(f"Get the git repo env file error")
                raise CustomException()
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Update the git repo env file error:{e}")
            raise CustomException()