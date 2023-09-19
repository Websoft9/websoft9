import time
import keyring
import json
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger
from src.external.nginx_proxy_manager_api import NginxProxyManagerAPI


class ProxyManager:
    def __init__(self, app_name):
        """
        Initialize the ProxyManager instance.

        Args:
            app_name (str): The name of the app
        """
        self.app_name = app_name
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
            token_json_str = keyring.get_password(service_name, token_name)
        except Exception as e:
            token_json_str = None

        # if the token is got from keyring, parse it
        if token_json_str is not None:
            try:
                token_json = json.loads(token_json_str)
                expires = token_json.get("expires")
                api_token = token_json.get("token")

                # if the token is not expired, return it
                if int(expires) - int(time.time()) > 3600:
                    self.nginx.set_token(api_token)
                    return
            except Exception as e:
                logger.error(f"Parse Nginx Proxy Manager's Token Error:{e}")
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
            expires = nginx_tokens.get("expires")
            api_token = nginx_tokens.get("token")

            self.nginx.set_token(api_token)

            token_json = {"expires": expires, "token": api_token}

            # set new token to keyring
            try:
                keyring.set_password(service_name, token_name, json.dumps(token_json))
            except Exception as e:
                logger.error(f"Set Nginx Proxy Manager's Token To Keyring Error:{e}")
                raise CustomException()
        else:
            raise CustomException()
            
    def check_proxy_host_exists(self,domain_names: list[str]):
        response = self.nginx.get_proxy_hosts()
        if response.status_code == 200:
            proxy_hosts = response.json()
            for proxy_host in proxy_hosts:
                if proxy_host["domain_names"] == domain_names:
                    return True
            return False
        else:
            raise CustomException()


    def create_proxy_for_app(self,domain_names: list[str],forward_host: str,forward_port: int,advanced_config: str = "",forward_scheme: str = "http"):
        try:
            self.nginx.create_proxy_host(
                domain_names=domain_names,
                forward_scheme=forward_scheme,
                forward_host=forward_host,
                forward_port=forward_port,
                advanced_config=advanced_config,
            )
        except Exception as e:
            logger.error(f"Create Proxy Host For {self.app_name} Error {e}")
            raise e
