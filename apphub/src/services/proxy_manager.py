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
    Proxy Manager
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
            print(jwt_token)
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
            
    def check_proxy_host_exists(self,domain_names: list[str]):
        """
        Check proxy host is exist

        Args:
            domain_names (list[str]): Domain names

        Returns:
            bool: True if proxy host is exist, False if proxy host is not exist, raise exception if error
        """
        response = self.nginx.get_proxy_hosts()
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
            logger.error(f"Check proxy host:{domain_names} exists error:{response.status_code}:{response.text}")
            raise CustomException()

    def create_proxy_by_app(self,domain_names: list[str],forward_host: str,forward_port: int,advanced_config: str = "",forward_scheme: str = "http"):
        response = self.nginx.create_proxy_host(
                domain_names=domain_names,
                forward_scheme=forward_scheme,
                forward_host=forward_host,
                forward_port=forward_port,
                advanced_config=advanced_config,
        )
        # if response.status_code == 201:
        #     return response.json()
        # elif response.status_code == 500:
        #     logger.error(f"Create proxy for app:{forward_host} error:{response.status_code}:{response.text}")
        #     raise CustomException()
        # else:
        #     logger.error(f"Create proxy for app:{forward_host} error:{response.status_code}:{response.text}")
        #     raise CustomException(
        #         status_code=400,
        #         message=f"Invalid Request",
        #         details=f"{json.loads(response.text).get('error',{}).get('message','Unknown Error')}"
        #     )
        if response.status_code != 201:
            logger.error(f"Create proxy for app:{forward_host} error:{response.status_code}:{response.text}")
            raise CustomException()
        else:
            return response.json()

    def update_proxy_by_app(self,proxy_id:int,domain_names: list[str],forward_host: str,forward_port: int,advanced_config: str = "",forward_scheme: str = "http"):
        response =  self.nginx.update_proxy_host(
                proxy_id=proxy_id,
                domain_names=domain_names,
                forward_scheme=forward_scheme,
                forward_host=forward_host,
                forward_port=forward_port,
                advanced_config=advanced_config,
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 500:
            logger.error(f"Update proxy for app:{forward_host} error:{response.status_code}:{response.text}")
            raise CustomException()
        else:
            logger.error(f"Update proxy for app:{forward_host} error:{response.status_code}:{response.text}")
            raise CustomException(
                status_code=400,
                message=f"Invalid Request",
                details=f"{json.loads(response.text).get('error',{}).get('message')}"
            )

    def get_proxy_host_by_app(self,app_id:str):
        response = self.nginx.get_proxy_hosts()
        if response.status_code == 200:
            proxys_host = response.json()
            proxy_result = []
            for proxy_host in proxys_host:
                if proxy_host.get("forward_host") == app_id:
                    # proxy_data = {
                    #     "proxy_id": proxy_host.get("id"),
                    #     "domain_names": proxy_host.get("domain_names")
                    # }
                    proxy_result.append(proxy_host)
            return proxy_result
        else:
            logger.error(f"Get proxy host by app:{app_id} error:{response.status_code}:{response.text}")
            raise CustomException()
    
    def remove_proxy_host_by_app(self,app_id:str):
        proxy_hosts = self.get_proxy_host_by_app(app_id)
        if proxy_hosts:
            for proxy_host in proxy_hosts:
                response = self.nginx.delete_proxy_host(proxy_host.get("id"))
                if response.status_code != 200:
                    logger.error(f"Remove proxy host:{proxy_host.get('id')} for app:{app_id} error:{response.status_code}:{response.text}")
                    raise CustomException()

    def remove_proxy_host_by_id(self,proxy_id:int):
        response = self.nginx.delete_proxy_host(proxy_id)
        if response.status_code != 200:
            logger.error(f"Remove proxy host:{proxy_id} error:{response.status_code}:{response.text}")
            raise CustomException()

    def get_proxy_hosts(self):
        response = self.nginx.get_proxy_hosts()
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Get proxy hosts error:{response.status_code}:{response.text}")
            raise CustomException()

    def get_proxy_host_by_id(self,proxy_id:int):
        proxy_hosts = self.get_proxy_hosts()
        try:
            for proxy_host in proxy_hosts:
                if proxy_host.get("id") == proxy_id:
                    return proxy_host
            return None
        except Exception as e:
            logger.error(f"Get proxy host by id:{proxy_id} error:{e}")
            raise CustomException()