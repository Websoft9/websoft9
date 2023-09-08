
import time
import keyring
import json
from app.core.logger import logger
from app.external.nginx_proxy_manager_api import NginxProxyManagerAPI


class DomainManager:
    def __init__(self, app_name):
        """
        Init Domain Manager
        Args:
            app_name (str): The name of the app
        """
        self.app_name = app_name
        try:
            self.nginx = NginxProxyManagerAPI()
            self._init_nginx_token()
        except Exception as e:
            logger.error(f"Init Nginx Proxy Manager API Error:{e}")
            raise e

    def _init_nginx_token(self):
        """
        Get Nginx Proxy Manager's Token From Keyring, if the token is expired or not got from keyring, get a new one and set it to keyring
        """
        service_name = 'nginx_proxy_manager'
        token_name = "nginx_token"

        # Try to get token from keyring
        try:
            token_json_str = keyring.get_password(service_name, token_name)
        except Exception as e:
            logger.error(f"Get Nginx Proxy Manager's Token From Keyring Error:{e}")
            token_json_str = None

        # if the token is got from keyring, parse it
        if token_json_str is not None:
            token_json = json.loads(token_json_str)
            expires = token_json.get("expires")
            api_token = token_json.get("token")

            # if the token is not expired, return it
            if int(expires) - int(time.time()) > 3600:
                self.nginx.api_token = api_token
                return

        # if the token is expired or not got from keyring, get a new one
        try:
            nginx_tokens = self.nginx.get_token("userName","userPwd")
        except Exception as e:
            logger.error(f"Get Nginx Proxy Manager's Token Error:{e}")
            return

        expires = nginx_tokens.get("expires")
        api_token = nginx_tokens.get("token")

        self.nginx.api_token = api_token

        token_json = {
            "expires": expires,
            "token": api_token
        }

        # set new token to keyring
        try:
            keyring.set_password(service_name, token_name, json.dumps(token_json))
        except Exception as e:
            logger.error(f"Set Nginx Proxy Manager's Token To Keyring Error:{e}")
            return
    
    def is_valid_domain(self, domain_names: list[str]):
        # 验证domain_names这个列表中的域名格式是否合法，如果不合法，返回以列表格式返回不合法的域名，如果合法，继续验证其是否解析到本机，如果没有解析到本机，返回以列表格式返回没有解析到本机的域名
        # 验证域名格式是否合法
        invalid_domain_names = []
        for domain_name in domain_names:
            if not self.nginx.is_valid_domain(domain_name):
                invalid_domain_names.append(domain_name)
        if len(invalid_domain_names) > 0:
            return False, invalid_domain_names
        # 验证域名是否解析到本机
        not_resolved_domain_names = []
        for domain_name in domain_names:
            if not self.nginx.is_resolved_domain(domain_name):
                not_resolved_domain_names.append(domain_name)
        if len(not_resolved_domain_names) > 0:
            return False, not_resolved_domain_names
        return True, None


    def create_proxy_for_app(self, domain_names:list[str],forward_port:int,advanced_config:str="",forward_scheme:str="http"):
        try:
            self.nginx.create_proxy_host(domain_names=domain_names,forward_scheme=forward_scheme,forward_port=forward_port,advanced_config=advanced_config)
        except Exception as e:
            logger.error(f"Create Proxy Host For {self.app_name} Error {e}")
            raise e