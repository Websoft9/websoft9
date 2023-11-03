from typing import List
from src.core.apiHelper import APIHelper
from src.core.config import ConfigManager


class NginxProxyManagerAPI:
    """
    This class provides methods to interact with the Nginx Proxy Manager API.
    Run the following command to start the Nginx Proxy Manager API:
    docker run -p 9090:8080 -e SWAGGER_JSON=/foo/api.swagger.json -v /data/websoft9/appmanage_new/docs/:/foo swaggerapi/swagger-ui

    Attributes:
        api (APIHelper): API helper

    Methods:
        set_token(api_token): Set API token
        get_token(identity, secret): Request a new access token
        get_proxy_hosts(): Get all proxy hosts
        create_proxy_host(domain_names, forward_scheme, forward_host, forward_port, advanced_config): Create a new proxy host
        update_proxy_host(proxy_id, domain_names, forward_scheme, forward_host, forward_port, advanced_config): Update an existing proxy host
        delete_proxy_host(proxy_id): Delete a proxy host
    """

    def __init__(self):
        """
        Initialize the NginxProxyManagerAPI instance.
        """
        self.api = APIHelper(
            ConfigManager().get_value("nginx_proxy_manager", "base_url"),
            {
                "Content-Type": "application/json",
            },
        )

    def set_token(self, api_token: str):
        """
        Set API token

        Args:
            api_token (str): API token
        """
        self.api.headers["Authorization"] = f"Bearer {api_token}"

    def get_token(self, identity: str, secret: str):
        """
        Request a new access token

        Args:
            identity (str): Identity
            secret (str): Secret

        Returns:
            Response: Response from Nginx Proxy Manager API
        """
        return self.api.post(
            path="tokens",
            headers={"Content-Type": "application/json"},
            json={"identity": identity, "scope": "user", "secret": secret},
        )

    def get_proxy_hosts(self):
        """
        get all proxy hosts

        Returns:
            Response: Response from Nginx Proxy Manager API
        """
        return self.api.get(
            path="nginx/proxy-hosts", params={"expand": "owner,access_list,certificate"}
        )

    def create_proxy_host(
        self,
        domain_names: List[str],
        forward_scheme: str,
        forward_host: str,
        forward_port: int,
        advanced_config: str,
    ):
        """
        Create a new proxy host

        Args:
            domain_names (List[str]): Domain names
            forward_scheme (str): Forward scheme
            forward_host (str): Forward host
            forward_port (int): Forward port
            advanced_config (str): Advanced config

        Returns:
            Response: Response from Nginx Proxy Manager API
        """
        return self.api.post(
            path="nginx/proxy-hosts",
            json={
                "domain_names": domain_names,
                "forward_scheme": forward_scheme,
                "forward_host": forward_host,
                "forward_port": forward_port,
                "access_list_id": "0",
                "certificate_id": 0,
                "meta": {"letsencrypt_agree": False, "dns_challenge": False},
                "advanced_config": advanced_config,
                "block_exploits": False,
                "caching_enabled": False,
                "allow_websocket_upgrade": False,
                "http2_support": False,
                "hsts_enabled": False,
                "hsts_subdomains": False,
                "ssl_forced": False,
                "locations": [],
            },
        )

    def update_proxy_host(
        self,proxy_id :int,json: dict
    ):
        """
        Update an existing proxy host

        Args:
            proxy_id (int): Proxy ID
            json (dict): Proxy host data

        Returns:
            Response: Response from Nginx Proxy Manager API
        """

        return self.api.put(
            path=f"nginx/proxy-hosts/{proxy_id}",
            json=json,
        )

    def delete_proxy_host(self, proxy_id: int):
        """
        Delete a proxy host

        Args:
            proxy_id (int): Proxy ID

        Returns:
            Response: Response from Nginx Proxy Manager API
        """
        return self.api.delete(path=f"nginx/proxy-hosts/{proxy_id}")
