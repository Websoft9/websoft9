
import ipaddress
import json
import os
import shutil
from src.core.config import ConfigManager
from src.core.envHelper import EnvHelper
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.schemas.appResponse import AppResponse
from src.schemas.proxyHosts import ProxyHost
from src.services.common_check import check_appId, check_appName_and_appVersion, check_domain_names, check_endpointId
from src.services.git_manager import GitManager
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.core.logger import logger
from src.services.proxy_manager import ProxyManager
from src.utils.file_manager import FileHelper
from src.utils.password_generator import PasswordGenerator


class AppManger:
    def get_catalog_apps(self,locale:str):
        try:
            # Get the app media path
            base_path = ConfigManager().get_value("app_media", "path")
            app_media_path = base_path + 'catalog_' + locale + '.json'
            # check the app media path is exists
            if not os.path.exists(app_media_path):
                logger.error(f"Get catalog apps error: {app_media_path} is not exists")
                raise CustomException()
            
            # Get the app catalog list
            with open(app_media_path, "r") as f:
                data = json.load(f)
                return data
        except (CustomException,Exception) as e:
            logger.error(f"Get catalog apps error:{e}")
            raise CustomException()

    def get_available_apps(self,locale:str):
        try:
            # Get the app media path
            base_path = ConfigManager().get_value("app_media", "path")
            app_media_path = base_path + 'product_' + locale + '.json'
            # check the app media path is exists
            if not os.path.exists(app_media_path):
                logger.error(f"Get available apps error: {app_media_path} is not exists")
                raise CustomException()
            
            # Get the app available list
            with open(app_media_path, "r") as f:
                data = json.load(f)
                # appAvailableResponses = [AppAvailableResponse(**item) for item in data]
                # return appAvailableResponses
                return data
        except (CustomException,Exception) as e:
            logger.error(f"Get available apps error:{e}")
            raise CustomException()

    def get_apps(self,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        try:
            apps_info = []
            # Get the stacks
            stacks = portainerManager.get_stacks(endpointId)
            for stack in stacks:
                stack_name = stack.get("Name",None)
                if stack_name is not None:
                    app_info = self.get_app_by_id(stack_name,endpointId)
                    apps_info.append(app_info)

            # Get the not stacks(not installed apps)
            all_containers = portainerManager.get_containers(endpointId)
            # Get the not stacks
            not_stacks = []
            for container in all_containers:
                container_labels = container.get("Labels",None)
                if container_labels is not None:
                    container_project = container_labels.get("com.docker.compose.project",None)
                    if container_project is not None:
                        if not any(container_project in stack.get("Name",[]) for stack in stacks):
                            not_stacks.append(container_project)
            # Remove the duplicate elements
            not_stacks = list(set(not_stacks))
            # Remove the websoft9
            if "websoft9" in not_stacks:
                not_stacks.remove("websoft9")
            # Get the not stacks info
            for not_stack in not_stacks:
                not_stack_response = AppResponse(
                    app_id=not_stack,
                    app_official=False,
                )
            apps_info.append(not_stack_response)

            return apps_info
        except (CustomException,Exception) as e:
            logger.error(f"Get apps error:{e}")
            raise CustomException()

    def get_app_by_id(self,app_id:str,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        
        # Get stack_info
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        # Get the stack_id
        stack_id = stack_info.get("Id",None)
        # Get the stack_status
        stack_status = stack_info.get("Status",0)
        # Get the gitConfig
        gitConfig = stack_info.get("GitConfig",{}) or {}
        # Get the creationDate
        creationDate = stack_info.get("CreationDate","")
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        
        # Get the domain_names
        domain_names = ProxyManager().get_proxy_host_by_app(app_id)
        # Get the proxy_enabled
        if not domain_names:
            proxy_enabled = False
        else :
            proxy_enabled = True
        # Get the volumes
        app_volumes = portainerManager.get_volumes_by_stack_name(app_id,endpointId,False)

        # if stack is empty(status=2-inactive),can not get it
        if stack_status == 1:
            # Get the containers
            app_containers = portainerManager.get_containers_by_stack_name(app_id,endpointId)
            
            # Get the main container
            main_container_id = None
            for container in app_containers:
                if f"/{app_id}" in container.get("Names", []):
                    main_container_id = container.get("Id", "")
                    break
            if main_container_id:
                # Get the main container info
                main_container_info =  portainerManager.get_container_by_id(endpointId, main_container_id)
            # Get the env
            app_env = main_container_info.get("Config", {}).get("Env", [])

            # Get http port from env
            app_http_port = None
            app_name = None
            app_dist = None
            for item in app_env:
                key, value = item.split("=", 1)
                if key == "APP_HTTP_PORT":
                    app_http_port = value
                elif key == "APP_NAME":
                    app_name = value
                elif key == "APP_DIST":
                    app_dist = value
                elif key == "APP_VERSION":
                    app_version = value

            # Get the app_port
            app_port = None
            if app_http_port:
                internal_port_str = str(app_http_port) + "/tcp"
                port_mappings = main_container_info["NetworkSettings"]["Ports"].get(internal_port_str, [])
                for mapping in port_mappings:
                    try:
                        ipaddress.IPv4Address(mapping["HostIp"])
                        app_port = mapping["HostPort"]
                    except ipaddress.AddressValueError:
                        continue
            
            appResponse = AppResponse(
                app_id = app_id,
                endpointId = endpointId,
                app_name = app_name,
                app_port = app_port,
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
                env = app_env
            )
            return appResponse
        else:
            appResponse = AppResponse(
                app_id = app_id,
                endpointId = endpointId,
                app_name = "",
                app_port = 0,
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
                env = []
            )
            return appResponse
    
    def install_app(self,appInstall: appInstall, endpointId: int = None):
        # Get the library path
        library_path = ConfigManager().get_value("docker_library", "path")

        # Get the portainer and gitea manager
        portainerManager = PortainerManager()
        giteaManager = GiteaManager()

        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
            
        # validate the app_name and app_version
        app_name = appInstall.app_name
        app_version = appInstall.edition.version
        check_appName_and_appVersion(app_name,app_version,library_path)

        # validate the app_id
        app_id = appInstall.app_id
        check_appId(app_id,endpointId,giteaManager,portainerManager)

        # validate the domain_names
        proxy_enabled = appInstall.proxy_enabled
        domain_names = appInstall.domain_names
        if proxy_enabled:
            check_domain_names(domain_names)

        # Install app - Step 1 : create repo in gitea
        repo_url =  giteaManager.create_repo(app_id)

        # Install app - Step 2 : initialize local git repo and push to gitea
        try:
            # The source directory.
            local_path = f"{library_path}/{app_name}"

            # Create a temporary directory.
            app_tmp_dir = "/tmp"
            app_tmp_dir_path = f"{app_tmp_dir}/{app_name}"

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
            new_env_values = {
                "APP_ID": app_id,
                "APP_NAME": app_name,
                "APP_DIST": "community",
                "APP_VERSION": app_version,
                "POWER_PASSWORD": PasswordGenerator.generate_strong_password(),
                "APP_URL": domain_names[0]
            }            
            EnvHelper(env_file_path).modify_env_values(new_env_values)
           
            # Commit and push to remote repo
            self._init_local_repo_and_push_to_remote(app_tmp_dir_path,repo_url)
        except (CustomException,Exception) as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
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
        except (CustomException,Exception) as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            raise CustomException()
        
        # Install app - Step 4 : create proxy in nginx proxy manager
        try:
            if proxy_enabled and domain_names:
                # Get the forward port form env file
                forward_port = EnvHelper(env_file_path).get_env_value_by_key("APP_HTTP_PORT")
                # Get the nginx proxy config path
                nginx_proxy_path = f"{app_tmp_dir_path}/src/nginx-proxy.conf"
                if os.path.exists(nginx_proxy_path):
                    # Get the advanced config
                    advanced_config = FileHelper.read_file(nginx_proxy_path)
                    ProxyManager().create_proxy_by_app(domain_names,app_id,forward_port,advanced_config)
                else:
                    ProxyManager().create_proxy_by_app(domain_names,app_id,forward_port)
        except (CustomException,Exception) as e:
            # Rollback-1: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Rollback-2: remove stack in portainer
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            raise CustomException()
        
        # Remove the tmp dir
        shutil.rmtree(app_tmp_dir_path)

        return self.get_app_by_id(app_id,endpointId)

    def redeploy_app(self,app_id:str,pull_image:bool,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
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

    def uninstall_app(self,app_id:str,purge_data:bool,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
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
                details=f"{app_id} is empty, can not uninstall it,you can remove it"
            )

        if purge_data:
            # Uninstall app - Step 1 : remove proxy in nginx proxy manager
            # Check the proxy is exists
            proxyManager = ProxyManager()
            proxys_host = proxyManager.get_proxy_host_by_app(app_id)
            # If the proxy is exists, remove it
            if proxys_host:
                proxyManager.remove_proxy_host_by_app(app_id)

            # Uninstall app - Step 2 : remove repo in gitea
            # Check the repo is exists
            giteaManager = GiteaManager()
            is_repo_exists = giteaManager.check_repo_exists(app_id)
            if is_repo_exists:
                giteaManager.remove_repo(app_id)
            
            # Uninstall app - Step 3 : remove stack in portainer
            # Get stack_id
            stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
            if stack_id is None:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"{app_id} Not Found"
                )
            # remove stack and volumes
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
        else:
            # down stack
            portainerManager.down_stack(stack_id,endpointId)

    def remove_app(self,app_id:str,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
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
                details=f"{app_id} is not empty, please uninstall it first"
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

    def start_app(self,app_id:str,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        # validate the app_id is exists in portainer
        # is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        # if not is_stack_exists:
        #     raise CustomException(
        #         status_code=400,
        #         message="Invalid Request",
        #         details=f"{app_id} Not Found"
        #     )
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is empty, can not start it,you can redeploy it"
            )
        
        portainerManager.start_stack(app_id,endpointId)

    def stop_app(self,app_id:str,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        # validate the app_id is exists in portainer
        # is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        # if not is_stack_exists:
        #     raise CustomException(
        #         status_code=400,
        #         message="Invalid Request",
        #         details=f"{app_id} Not Found"
        #     )
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is empty, can not stop it,you can redeploy it"
            )
        portainerManager.stop_stack(app_id,endpointId)

    def restart_app(self,app_id:str,endpointId:int = None):
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        # validate the app_id is exists in portainer
        # is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        # if not is_stack_exists:
        #     raise CustomException(
        #         status_code=400,
        #         message="Invalid Request",
        #         details=f"{app_id} Not Found"
        #     )
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is empty, can not restart it,you can redeploy it"
            )
        portainerManager.restart_stack(app_id,endpointId)
        
    def get_proxys_by_app(self,app_id:str,endpointId:int = None):
        portainerManager = PortainerManager()
        proxyManager = ProxyManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # stack_status = stack_info.get("Status",None)
        # if stack_status == 2:
        #     raise CustomException(
        #         status_code=400,
        #         message="Invalid Request",
        #         details=f"{app_id} is inactive, can not get proxy,you can redeploy it"
        #     )
        # Get the proxys
        proxys_host = proxyManager.get_proxy_host_by_app(app_id)
        return proxys_host

    def create_proxy_by_app(self,app_id:str,domain_names:list[str],endpointId:int = None):
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
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
        
        # Check the domain_names
        check_domain_names(domain_names)

        # Get the forward port
        stack_env = self.get_app_by_id(app_id,endpointId).env
        if stack_env:
            for item in stack_env:
                key, value = item.split("=", 1)
                if key == "APP_HTTP_PORT":
                    forward_port = value
                    break
            # Create proxy
            if forward_port:
                proxy_host = proxyManager.create_proxy_by_app(domain_names,app_id,forward_port)
                if proxy_host:
                    return ProxyHost(
                        proxy_id=proxy_host.get("id"),
                        domain_names=proxy_host.get("domain_names"),
                    )
                else:
                    raise CustomException()
            else:
                raise CustomException()
        else:
            raise CustomException()

    def remove_proxy_by_app(self,app_id:str,endpointId:int = None):
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        # Check the app_id is exists
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        
        domain_names = proxyManager.get_proxy_host_by_app(app_id)
        if not domain_names:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is not exists proxy"
            )

        # Remove proxy
        proxyManager.remove_proxy_host_by_app(app_id)

    def remove_proxy_by_id(self,proxy_id:int):
        # Check the proxy id is exists
        host = ProxyManager().get_proxy_host_by_id(proxy_id)
        if host is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"Proxy ID:{proxy_id} Not Found"
            )
        ProxyManager().remove_proxy_host_by_id(proxy_id)

    def update_proxy_by_app(self,app_id:str,proxyHost:ProxyHost,endpointId:int = None):
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        endpointId = check_endpointId(endpointId, portainerManager)
        
        # Check the app_id is exists
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        
        # Check the proxy id is exists
        host = proxyManager.get_proxy_host_by_id(proxyHost.proxy_id)
        if host is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"Proxy ID:{proxyHost.proxy_id} Not Found"
            )
        
        # Check the domain_names

        # Update proxy
        proxy_host = proxyManager.update_proxy_by_app(
            proxyHost.proxy_id,
            proxyHost.domain_names,
            host.get("forward_host"),
            host.get("forward_port"),
            host.get("advanced_config"),
            host.get("forward_scheme")
        )

        if proxy_host:
            return ProxyHost(
                proxy_id=proxy_host.get("id"),
                domain_names=proxy_host.get("domain_names"),
            )
        else:
            raise CustomException()

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

    