import time
import jwt
import keyring
import json
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger
from src.external.nginx_proxy_manager_api import NginxProxyManagerAPI


class ProxyManager:
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
        response = self.nginx.get_proxy_hosts()
        if response.status_code == 200:
            proxy_hosts = response.json()
            matching_domains = []
            for proxy_host in proxy_hosts:
                matching_domains += [domain for domain in domain_names if domain in proxy_host.get("domain_names", [])]

            if matching_domains:
                raise CustomException(
                    status_code=400,
                    message=f"Proxy Host Already Used",
                    details=f"matching_domains:{matching_domains} already used"
                )
        else:
            raise CustomException()


    def create_proxy_for_app(self,domain_names: list[str],forward_host: str,forward_port: int,advanced_config: str = "",forward_scheme: str = "http"):
        response = self.nginx.create_proxy_host(
                domain_names=domain_names,
                forward_scheme=forward_scheme,
                forward_host=forward_host,
                forward_port=forward_port,
                advanced_config=advanced_config,
        )
        if response.status_code != 201:
            logger.error(f"Error create proxy for app:{response.text}")
            raise CustomException()


    def update_proxy_for_app(self,domain_names: list[str],forward_host: str,forward_port: int,advanced_config: str = "",forward_scheme: str = "http"):
        response =  self.nginx.update_proxy_host(
                domain_names=domain_names,
                forward_scheme=forward_scheme,
                forward_host=forward_host,
                forward_port=forward_port,
                advanced_config=advanced_config,
        )
        if response.status_code != 200:
            logger.error(f"Error update proxy for app:{response.text}")
            raise CustomException()
