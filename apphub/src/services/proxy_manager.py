import json
import time
import jwt
import keyring
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger
from src.external.nginx_proxy_manager_api import NginxProxyManagerAPI

class ProxyManager:
    """
    This class is used to manage proxy hosts

    Attributes:
        nginx (NginxProxyManagerAPI): The Nginx Proxy Manager API instance

    Methods:
        check_proxy_host_exists: Check proxy host is exist
        create_proxy_by_app: Create a proxy host
        update_proxy_by_app: Update a proxy host
        get_proxy_host_by_app: Get proxy host by app
        remove_proxy_host_by_app: Remove proxy host by app
        remove_proxy_host_by_id: Remove proxy host by id
        get_proxy_hosts: Get proxy hosts
        get_proxy_host_by_id: Get proxy host by id
    """
    def __init__(self):
        """
        Initialize the ProxyManager instance.

        Args:
            app_name (str): The name of the app
        """
        try:
            self.nginx = NginxProxyManagerAPI()
            self._set_nginx_token()
        except Exception as e:
            logger.error(f"Init Nginx Proxy Manager API Error:{e}")
            raise CustomException() 

    def _set_nginx_token(self):
        """
        Get Nginx Proxy Manager's Token From Keyring, if the token is expired or not got from keyring, get a new one and set it to keyring
        """
        service_name = "nginx_proxy_manager"
        token_name = "user_token"

        # Try to get token from keyring
        try:
            jwt_token = keyring.get_password(service_name, token_name)
        except Exception as e:
            jwt_token = None

        # if the token is got from keyring, parse it
        if jwt_token is not None:
            try:
                decoded_jwt = jwt.decode(jwt_token, options={"verify_signature": False})
                exp_timestamp = decoded_jwt['exp']

                # if the token is not expired, return it
                if int(exp_timestamp) - int(time.time()) > 3600:
                    self.nginx.set_token(jwt_token)
                    return
            except Exception as e:
                logger.error(f"Decode Nginx Proxy Manager's Token Error:{e}")
                raise CustomException()

        # if the token is expired or not got from keyring, get a new one
        try:
            userName = ConfigManager().get_value("nginx_proxy_manager", "user_name")
            userPwd = ConfigManager().get_value("nginx_proxy_manager", "user_pwd")
        except Exception as e:
            logger.error(f"Get Nginx Proxy Manager's UserName and UserPwd Error:{e}")
            raise CustomException()
        
        nginx_tokens = self.nginx.get_token(userName, userPwd)
        if nginx_tokens.status_code == 200:
            nginx_tokens = nginx_tokens.json()
            jwt_token = nginx_tokens.get("token")
            self.nginx.set_token(jwt_token)
            # set new token to keyring
            try:
                keyring.set_password(service_name, token_name, jwt_token)
            except Exception as e:
                logger.error(f"Set Nginx Proxy Manager's Token To Keyring Error:{e}")
                raise CustomException()
        else:
            raise CustomException()

    def _handler_nginx_error(self,response):
        """
        Handler Nginx Proxy Manager API Error

        Args:
            response (Response): Response
        """
        logger.access(f"Nginx error handler called with status: {response.status_code}")
        logger.access(f"Nginx error response text: {response.text}")
        # If status_code is 500, raise CustomException
        if response.status_code == 500:
            logger.error(f"Nginx Proxy Manager API Error:{response.status_code}:{response.text}")
            raise CustomException()
        else:
            # Get error message from response
            response_dict = json.loads(response.text)
            error_dict = response_dict.get('error', {})
            details = error_dict.get('message','Unknown Error')
            logger.access(f"Extracted error details: {details}")
            raise CustomException(
                status_code=400,
                message=f"Invalid Request",
                details=details
            )
        
    def check_proxy_host_exists(self,domain_names: list[str]):
        """
        Check proxy host is exist

        Args:
            domain_names (list[str]): Domain names

        Returns:
            bool: True if proxy host is exist, False if proxy host is not exist, raise exception if error
        """
        response = self.nginx.get_proxy_hosts()
        try:
            if response.status_code == 200:
                proxy_hosts = response.json()
                matching_domains = []
                for proxy_host in proxy_hosts:
                    matching_domains += [domain for domain in domain_names if domain in proxy_host.get("domain_names", [])]

                if matching_domains:
                    raise CustomException(
                        status_code=400,
                        message=f"Invalid Request",
                        details=f"{matching_domains} already used"
                    )
            else:
                self._handler_nginx_error(response)
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Check proxy host:{domain_names} exists error:{e}")
            raise CustomException()

    def create_proxy_by_app(self,domain_names: list[str],forward_host: str,forward_port: int,advanced_config: str = "",forward_scheme: str = "http"):
        """
        Create a proxy host

        Args:
            domain_names (list[str]): Domain names
            forward_host (str): Forward host
            forward_port (int): Forward port
            advanced_config (str, optional): Advanced config. Defaults to "".
            forward_scheme (str, optional): Forward scheme. Defaults to "http".

        Returns:
            dict: Proxy host
        """
        response = self.nginx.create_proxy_host(
                domain_names=domain_names,
                forward_scheme=forward_scheme,
                forward_host=forward_host,
                forward_port=forward_port,
                advanced_config=advanced_config,
        )
        if response.status_code != 201:
            self._handler_nginx_error(response)
        else:
            return response.json()

    def update_proxy_by_app(self,proxy_id:int,domain_names: list[str]):
        """
        Update a proxy host

        Args:
            proxy_id (int): Proxy id
            domain_names (list[str]): Domain names

        Returns:
            dict: Proxy host
        """
        # Get proxy host by id
        req_json = self.get_proxy_host_by_id(proxy_id)
        try:
            if req_json is None:
                raise CustomException(
                    status_code=400,
                    message=f"Invalid Request",
                    details=f"Proxy host:{proxy_id} not found"
                )
            # update domain_names
            req_json["domain_names"] = domain_names
            # delete useless keys from req_json(because the req_json is from get_proxy_host_by_id and update_proxy_host need less keys)
            keys_to_delete = ["id","created_on","modified_on","owner_user_id","enabled","certificate","owner","access_list","use_default_location","ipv6"]
            for key in keys_to_delete:
                req_json.pop(key, None) 

            response =  self.nginx.update_proxy_host(proxy_id=proxy_id, json=req_json)
            if response.status_code == 200:
                return response.json()
            else:
                self._handler_nginx_error(response)
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Update proxy host:{proxy_id} error:{e}")
            raise CustomException()

    def update_proxy_port_by_app(self, proxy_id: int, forward_port: int):
        """
        Update a proxy host's forward port

        Args:
            proxy_id (int): Proxy id
            forward_port (int): Forward port

        Returns:
            dict: Proxy host
        """
        # Get proxy host by id
        req_json = self.get_proxy_host_by_id(proxy_id)
        try:
            if req_json is None:
                raise CustomException(
                    status_code=400,
                    message=f"Invalid Request",
                    details=f"Proxy host:{proxy_id} not found"
                )
            # update forward_port
            req_json["forward_port"] = forward_port
            # delete useless keys from req_json(because the req_json is from get_proxy_host_by_id and update_proxy_host need less keys)
            keys_to_delete = ["id", "created_on", "modified_on", "owner_user_id", "enabled", "certificate", "owner", "access_list", "use_default_location", "ipv6"]
            for key in keys_to_delete:
                req_json.pop(key, None)

            response = self.nginx.update_proxy_host(proxy_id=proxy_id, json=req_json)
            if response.status_code == 200:
                return response.json()
            else:
                self._handler_nginx_error(response)
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Update proxy host:{proxy_id} error:{e}")
            raise CustomException()

    def get_proxy_host_by_app(self,app_id:str):
        """
        Get proxy host by app

        Args:
            app_id (str): App id

        Returns:
            list[dict]: Proxy hosts
        """
        response = self.nginx.get_proxy_hosts()
        try:
            if response.status_code == 200:
                proxys_host = response.json()
                proxy_result = []
                for proxy_host in proxys_host:
                    if proxy_host.get("forward_host") == app_id:
                        proxy_result.append(proxy_host)
                return proxy_result
            else:
                self._handler_nginx_error(response)
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Get proxy host by app:{app_id} error:{e}")
            raise CustomException()
    
    def remove_proxy_host_by_app(self,app_id:str):
        """
        Remove proxy host by app

        Args:
            app_id (str): App id
        """
        proxy_hosts = self.get_proxy_host_by_app(app_id)
        try:
            if proxy_hosts:
                for proxy_host in proxy_hosts:
                    response = self.nginx.delete_proxy_host(proxy_host.get("id"))
                    if response.status_code != 200:
                        self._handler_nginx_error(response)
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Remove proxy host by app:{app_id} error:{e}")
            raise CustomException()

    def remove_proxy_host_by_id(self,proxy_id:int):
        """
        Remove proxy host by id

        Args:
            proxy_id (int): Proxy id
        """
        response = self.nginx.delete_proxy_host(proxy_id)
        if response.status_code != 200:
            self._handler_nginx_error(response)

    def get_proxy_hosts(self):
        """
        Get proxy hosts

        Returns:
            list[dict]: Proxy hosts
        """
        response = self.nginx.get_proxy_hosts()
        if response.status_code == 200:
            return response.json()
        else:
            self._handler_nginx_error(response)

    def get_proxy_host_by_id(self,proxy_id:int):
        """
        Get proxy host by id

        Args:
            proxy_id (int): Proxy id

        Returns:
            dict: Proxy host
        """
        proxy_hosts = self.get_proxy_hosts()
        try:
            for proxy_host in proxy_hosts:
                if proxy_host.get("id") == proxy_id:
                    return proxy_host
            return None
        except Exception as e:
            logger.error(f"Get proxy host by id:{proxy_id} error:{e}")
            raise CustomException()

    def get_all_certificates(self):
        """
        Get all certificates

        Returns:
            list[dict]: Certificates
        """
        response = self.nginx.get_certificates()
        if response.status_code == 200:
            return response.json()
        else:
            self._handler_nginx_error(response)