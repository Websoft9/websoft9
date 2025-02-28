import base64
import json
import os
import shutil
import random
import ipaddress
import yaml
import time
import docker
import requests
import asyncio
import aiodocker
from typing import Tuple
from datetime import datetime
from src.core.config import ConfigManager
from src.core.envHelper import EnvHelper
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.schemas.appResponse import AppResponse
from src.services.common_check import check_apps_number, check_endpointId
from src.services.git_manager import GitManager
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.core.logger import logger
from src.services.proxy_manager import ProxyManager
from src.utils.async_utils import AsyncWrapper
from src.utils.file_manager import FileHelper
from src.utils.password_generator import PasswordGenerator
from tenacity import retry, stop_after_attempt, wait_fixed

from src.services.app_status import appInstalling, appInstallingError,start_app_installation,remove_app_installation,modify_app_information,remove_app_from_errors_by_app_id,add_installing_logs,remove_installation_logs


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

            # Get the initial_apps from config.ini
            initial_apps = ConfigManager("config.ini").get_value("initial_apps", "keys")
            if not initial_apps:
                return data
            else:
                app_keys = initial_apps.split(",")
                return [item for item in data if item.get("key") in app_keys]
            
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
                        logs = app.get("logs", None)
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
                        logs = None
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
        try:
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
                    parts  = item.split("=", 1)
                    if len(parts) == 2:
                        key, value = parts
                    else:
                        key = parts[0]
                        value = "" 
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
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Get app by app_id:{app_id} error:{e}")
            raise CustomException()
    
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
        add_installing_logs(app_uuid, "Initializing installation","")

        # Install app - Step 1 : create repo in gitea
        try:
            repo_url =  giteaManager.create_repo(app_id)
        except CustomException as e:
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # modify app status: error
            modify_app_information(app_uuid,"Create repo error")
            remove_installation_logs(app_uuid)
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

            # The temporary directory path.
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
            envHelper.set_value("W9_ID", app_id)
            envHelper.set_value("W9_APP_NAME", app_name)
            envHelper.set_value("W9_DIST", "community")
            envHelper.set_value("W9_VERSION", app_version)

            # Verify if a rcode needs to be set
            is_set_rcode = envHelper.get_value("W9_RCODE")
            if is_set_rcode is not None:
                # Set the rcode to env file
                envHelper.set_value("W9_RCODE", PasswordGenerator.generate_random_string_with_rules(12))
            
            # Verify if a password needs to be set
            is_set_password = envHelper.get_value("W9_POWER_PASSWORD")
            if is_set_password is not None:
                # Set the password to env file
                envHelper.set_value("W9_POWER_PASSWORD", PasswordGenerator.generate_strong_password())

            # Set the settings to env file
            if settings:
                for key, value in settings.items():
                    envHelper.set_value(key, value)

            # Verify the app is web app
            is_web_app = envHelper.get_value("W9_URL")
            # url_with_port = envHelper.get_value("W9_URL_WITH_PORT")
            w9_url_with_replace = envHelper.get_value("W9_URL_REPLACE")

            if is_web_app is not None:
                if w9_url_with_replace is None:
                    envHelper.set_value("W9_URL", domain_names[0])
                else:
                    try:
                        ipaddress.ip_address(domain_names[0])
                        #envHelper.set_value("W9_URL", domain_names[0] + ":" + envHelper.get_value("W9_HTTP_PORT_SET"))
                        envHelper.set_value("W9_URL", domain_names[0] + ":" + (envHelper.get_value("W9_HTTP_PORT_SET") or envHelper.get_value("W9_HTTPS_PORT_SET")))
                    except ValueError:
                        envHelper.set_value("W9_URL", domain_names[0])

            # if is_web_app is not None and url_with_port is not None:
            #     try:
            #         ipaddress.ip_address(domain_names[0])
            #         envHelper.set_value("W9_URL", domain_names[0] + ":" + envHelper.get_value("W9_HTTP_PORT_SET"))
            #     except ValueError:
            #         envHelper.set_value("W9_URL", domain_names[0])
                    
            # Commit and push to remote repo
            self._init_local_repo_and_push_to_remote(app_tmp_dir_path,repo_url)
        except CustomException as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid,"Initialize repo error")
            remove_installation_logs(app_uuid)
            logger.error(f"Initialize repo error:{e}")
            raise CustomException()

        # Install app - Step 3 : pull docker image
        try:
            add_installing_logs(app_uuid,"Pulling docker image","")
            self.pull_images_from_yml(app_tmp_dir_path,app_uuid)
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid, "Pull docker image error")
            remove_installation_logs(app_uuid)
            logger.error(f"Pull docker image error: {e}")
            raise CustomException()

        # Install app - Step 4 : create stack in portainer
        try:
            add_installing_logs(app_uuid,"Starting the services","")
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
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Remove volumes
            portainerManager.remove_vloumes(app_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,"Create stack error")
            remove_installation_logs(app_uuid)
            logger.error(f"Create stack error:{e}")
            raise CustomException()
            
        # Install app - Step 5 : create proxy in nginx proxy manager
        try:
            add_installing_logs(app_uuid,"Configuring the domain","")
            # check the app is web app
            if is_web_app is not None :
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
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # Rollback-1: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Rollback-2: remove stack in portainer
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,"Create proxy error")
            remove_installation_logs(app_uuid)
            logger.error(f"Create proxy error:{e}")
            raise CustomException()

        # remove app from installing
        remove_app_installation(app_uuid)

        # Remove the tmp dir
        shutil.rmtree(app_tmp_dir_path)

        logger.access(f"Installed app: [{app_id}]")
        add_installing_logs(app_uuid,"Installation complete","")
        # 等待1秒
        time.sleep(1)

    async def redeploy_app(self,app_id:str,pull_image:bool,endpointId:int = None,queue: asyncio.Queue = None):
        """
        Redeploy app

        Args:
            app_id (str): The app id.
            pull_image (bool): Whether to pull the image when redeploying the app.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        async def send_log(message: str):
            if queue:
                await queue.put(message)
                
        await send_log("Initializing Redeployment")
        # Get the appInstallApps
        appInstallApps = AppManger().get_apps(endpointId)

        # Get all apps that are official and active
        app_official = [app for app in appInstallApps if app.app_official == True and app.status == 1 ]

        # if app_id is active,can not check the apps number
        if not any(app.app_id == app_id for app in app_official):
            # Chenck the apps number
            check_apps_number(endpointId)

        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
            check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        await send_log("Verify Application Status")
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

            app_tmp_dir = f"/tmp/{app_id}"
            # if the app_tmp_dir exists, remove it
            if os.path.exists(app_tmp_dir):
                shutil.rmtree(app_tmp_dir)

            # instantiate a GitManager object
            gitManager =GitManager(app_tmp_dir) 

            # 从app中获取 gitConfig属性的URL属性值
            remote_url = [app.gitConfig.get("URL") for app in app_official if app.app_id == app_id][0]

            # Initialize a local git repository from a directory
            gitManager.clone_remote_repo_to_local(remote_url,user_name,user_pwd)
            
            env_file_path = os.path.join(app_tmp_dir, '.env')
            env_helper = EnvHelper(env_file_path)
            yml_files = [os.path.join(app_tmp_dir, f) for f in os.listdir(app_tmp_dir) if f.endswith('.yml')]

            if not yml_files:
                raise CustomException("No yml files found in the directory")

            # Initialize Docker client with host's Docker socket
            docker_client = aiodocker.Docker()

            async def docker_pull_image(image):
                success = False  # 标志位，跟踪是否成功拉取镜像
                try:
                    # Try pulling the image directly first
                    await send_log(f"Pulling image: {image}")
                    pull_result = docker_client.images.pull(image, stream=True)
                    async for line in pull_result:
                        await send_log(line)
                    success = True  # 成功拉取镜像
                    return
                # except docker.errors.APIError as e:
                #     pass
                except Exception as e:
                    await send_log(f"Failed to pull image: {image}")
                    pass

                 # Get image accelerators
                image_accelerators = self.download_image_accelerators()

                # If direct pull fails, try using accelerators
                for accelerator in image_accelerators:
                    try:
                        # Replace the image name with the accelerator URL
                        accelerated_image = f"{accelerator}/{image}"
                        await send_log(f"Pulling image: {accelerated_image}")
                        pull_result = docker_client.images.pull(accelerated_image, stream=True)
                        async for line in pull_result:
                            await send_log(line)
                        
                        # Tag the image back to its original name
                        await docker_client.images.tag(accelerated_image, image)
                        # Remove the accelerated image tag
                        await docker_client.images.delete(accelerated_image)
                        success = True  # 成功拉取镜像
                        break
                    except docker.errors.APIError as e:
                        logger.error(f"Failed to pull image from {accelerator}: {e}")
                
                # If all attempts fail, raise an exception
                if not success:
                    raise CustomException(f"Failed to pull image: {image}")

            tasks = []
            for yml_file in yml_files:
                with open(yml_file, 'r') as file:
                    compose_content = yaml.safe_load(file)
                    services = compose_content.get('services', {})
                    for service in services.values():
                        image = service.get('image')
                        if image:
                            # Replace environment variables in the image string
                            image = self._replace_env_variables(image, env_helper)
                            if pull_image: 
                                tasks.append(docker_pull_image(image)) #强制拉取镜像
                            try:
                                # Check if the image already exists
                                await docker_client.images.get(image)
                                continue
                            except aiodocker.exceptions.DockerError:
                                tasks.append(docker_pull_image(image))

            await asyncio.gather(*tasks)

            docker_client.close()

            await send_log("Redeploying stack")
            # redeploy stack

            # portainerManager.redeploy_stack(stack_id,endpointId,pull_image,user_name,user_pwd)
            try:
                await AsyncWrapper.run_sync(
                    portainerManager.redeploy_stack,
                    stack_id,
                    endpointId,
                    False,      #强制设置不拉取镜像，而是通过Websoft9的逻辑来拉取镜像
                    user_name,
                    user_pwd,
                    timeout=60  # 自定义超时
                )
            except CustomException as e:
                await send_log(f"Redeploy stack error: {e}")
                raise e
            
            # Remove the tmp dir
            shutil.rmtree(app_tmp_dir)


            app_info = self.get_app_by_id(app_id,endpointId)
            forward_ports = [domain.get("forward_port") for domain in app_info.domain_names]

            proxy_ids = [domain.get("id") for domain in app_info.domain_names]

            if forward_ports:
                http_port = app_info.env.get("W9_HTTP_PORT")
                https_port = app_info.env.get("W9_HTTPS_PORT")

                forward_port = http_port if http_port else https_port

                forward_ports_str = [str(port) for port in forward_ports]

                if not all(port == forward_port for port in forward_ports_str):
                    for proxy_id in proxy_ids:
                        ProxyManager().update_proxy_port_by_app(proxy_id, forward_port)
                        logger.access(f"Updated proxy port: {forward_port} for app: {app_id}")
            
            await send_log("Redeployment complete")
            # 等待1秒
            time.sleep(5)
            #await send_log(None)
            logger.access(f"Redeployed app: [{app_id}]")
            

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
            logger.access(f"Uninstalled app: [{app_id}] and removed all data")
        else:
            # down stack
            portainerManager.down_stack(stack_id,endpointId)
            logger.access(f"Uninstalled app: [{app_id}] and keep data")

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

        logger.access(f"Removed app: [{app_id}]")

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

        logger.access(f"Removed error app: [{app_id}]")

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
        logger.access(f"Started app: [{app_id}]")

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
        logger.access(f"Stopped app: [{app_id}]")

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
        logger.access(f"Restarted app: [{app_id}]")
        
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


                # Get the nginx proxy config
                advanced_config = GiteaManager().get_file_raw_from_repo(app_id, "src/nginx-proxy.conf")
                if advanced_config:
                    proxy_host = proxyManager.create_proxy_by_app(domain_names, app_id, forward_port, advanced_config, forward_scheme=forward_scheme)
                else:
                    proxy_host = proxyManager.create_proxy_by_app(domain_names, app_id, forward_port, forward_scheme=forward_scheme)

                if proxy_host:
                    logger.access(f"Created domains: {domain_names} for app: [{app_id}]")
                    return proxy_host
                else:
                    logger.error(f"Failed to create proxy host for app: [{app_id}]")
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
        logger.access(f"Removed all domains for app: [{app_id}]")

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
                                    # 如果w9_url_with_port存在，并且值为: true
                                        new_w9_url = client_host+":"+ (app_info.env.get("W9_HTTP_PORT_SET") or app_info.env.get("W9_HTTPS_PORT_SET"))
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
                    logger.access(f"Removed domains:{host['domain_names']} for app: [{app_id}]")
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
        logger.access(f"Updated domains:{domain_names} for app: [{host['forward_host']}]")
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

    def _replace_env_variables(self, text: str, env_helper: EnvHelper) -> str:
        """
        Replace environment variables in the given text using values from env_helper.

        Args:
            text (str): The text containing environment variables.
            env_helper (EnvHelper): The EnvHelper instance to get environment variable values.

        Returns:
            str: The text with environment variables replaced.
        """
        for key, value in env_helper.get_all_values().items():
            text = text.replace(f"${{{key}}}", value)
            text = text.replace(f"${key}", value)
        return text

    @retry(stop=stop_after_attempt(10), wait=wait_fixed(1))
    def download_image_accelerators(self):
        try:
            url = ConfigManager("config.ini").get_value("docker_mirror", "url")
            response = requests.get(url)
            if response.status_code != 200:
                logger.error(f"Failed to download image accelerators: {response.text}")
                raise CustomException("Failed to download image accelerators")
            return response.json().get("mirrors", [])
        except Exception as e:
            logger.error(f"Failed to download image accelerators: {e}")
            return []

    def pull_images_from_yml(self, app_tmp_dir_path, app_uuid):
        logger.access(f"Pulling images from yml files in {app_tmp_dir_path}")
        env_file_path = os.path.join(app_tmp_dir_path, '.env')
        env_helper = EnvHelper(env_file_path)
        yml_files = [os.path.join(app_tmp_dir_path, f) for f in os.listdir(app_tmp_dir_path) if f.endswith('.yml')]

        if not yml_files:
            raise CustomException("No yml files found in the directory")

        # Get image accelerators
        image_accelerators = self.download_image_accelerators()

        # Initialize Docker client with host's Docker socket
        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')

        def pull_image(image):
            success = False  # 标志位，跟踪是否成功拉取镜像
            try:
                logger.access(f"Pulling image: {image}")
                # Try pulling the image directly first
                for line in docker_client.api.pull(image, stream=True, decode=True):
                    add_installing_logs(app_uuid,"Pulling docker image",line)
                success = True  # 成功拉取镜像
                return
            # except docker.errors.APIError as e:
            #     # Nothing to do
            #     pass
            except Exception as e:
                pass

            # If direct pull fails, try using accelerators
            for accelerator in image_accelerators:
                try:
                    # Replace the image name with the accelerator URL
                    accelerated_image = f"{accelerator}/{image}"
                    logger.access(f"Pulling image from {accelerator}: {accelerated_image}")
                    for line in docker_client.api.pull(accelerated_image, stream=True, decode=True):
                        add_installing_logs(app_uuid,"Pulling docker image",line)
                    
                    # Tag the image back to its original name
                    docker_client.api.tag(accelerated_image, image)
                    # Remove the accelerated image tag
                    docker_client.api.remove_image(accelerated_image)
                    success = True  # 成功拉取镜像
                    return
                except docker.errors.APIError as e:
                    logger.error(f"Failed to pull image from {accelerator}: {e}")
            
                if not success:
                    raise CustomException(f"Failed to pull image: {image}")

        for yml_file in yml_files:
            with open(yml_file, 'r') as file:
                compose_content = yaml.safe_load(file)
                services = compose_content.get('services', {})
                for service in services.values():
                    image = service.get('image')
                    if image:
                        # Replace environment variables in the image string
                        image = self._replace_env_variables(image, env_helper)
                        try:
                            # Check if the image already exists
                            logger.access(f"Checking if image exists: {image}")
                            docker_client.images.get(image)
                            continue
                        except docker.errors.ImageNotFound:
                            logger.access(f"Image not found: {image}")
                            pull_image(image)