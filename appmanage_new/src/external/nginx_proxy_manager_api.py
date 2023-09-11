
import requests
from typing import List, Union
from src.core.config import ConfigManager

class NginxProxyManagerAPI:
    """
    This class provides methods to interact with the Nginx Proxy Manager API.

    Attributes:
        base_url (str): The base URL of the Nginx Proxy Manager API.
        api_token (str): The API Token to use for authorization.

    Methods:
        get_token(identity: str,secret: str): Request a new access token
        refresh_token(): Refresh your access token
        get_proxy_hosts(): Get all proxy hosts
        create_proxy_host(domain_names: List[str],forward_scheme:str,forward_host: str,forward_port: int ,advanced_config: str): Create a new proxy host
        update_proxy_host(proxy_id: int,domain_names: List[str],forward_scheme:str,forward_host: str,forward_port: int ,advanced_config: str): Update an existing proxy host
        delete_proxy_host(proxy_id: int): Delete a proxy host
    """

    def __init__(self):
        """
        Initialize the NginxProxyManagerAPI instance.
        """
        self.base_url = ConfigManager().get_value("nginx_proxy_manager", "base_url")
        self.api_token = None

    def get_token(self, identity: str, secret: str) -> Union[dict, None]:
        """
        Request a new access token

        Args:
            identity (string): user account with an email address
            secret (string): user password

        Returns:
            dict or None: A dictionary containing token-related information if successful,otherwise None. The dictionary structure is as follows:                
                If successful:
                {
                    "expires": str,   # Expiry timestamp of the token
                    "token": str      # The access token
                }

                If unsuccessful:
                None
         """

        url = f"{self.base_url}/api/tokens"
        headers = {
            'Content-Type': 'application/json'
        }
        json = {
            "identity": identity,
            "scope": "user",
            "secret": secret
        }
        response = requests.post(url, json=json, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None
        
    def refresh_token(self) -> Union[dict, None]:
        """
        Refresh your access token

        Returns:
            dict or None: A dictionary containing token-related information if successful,otherwise None. The dictionary structure is as follows:                
                If successful:
                {
                    "expires": str,   # Expiry timestamp of the token
                    "token": str      # The access token
                }

                If unsuccessful:
                None
        """
        url = f"{self.base_url}/api/tokens"
        headers = {
            'Content-Type': 'application/json',
            "Authorization": f"Bearer {self.api_token}"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return  response.json()
        else:
            return None

    def get_proxy_hosts(self) -> Union[List[dict], None]:
        """
        Get all proxy hosts

        Returns:
            list or None: If the retrieval is successful, returns a list of dictionaries containing proxy host information, where each dictionary includes:
                - "proxy_id": The ID of the proxy host.
                - "forward_host": The target host name of the proxy.
                - "domain_names": A list of domain names associated with the proxy host.
            Returns None if the retrieval fails.
        """
        url = f"{self.base_url}/api/nginx/proxy-hosts"
        params = {"expand": "owner,access_list,certificate"}
        headers = {
            'Content-Type': 'application/json',
            "Authorization": f"Bearer {self.api_token}"
        }
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            proxy_hosts = response.json()
            result_dict = [
                {
                    "proxy_id": proxy["id"],
                    "forward_host": proxy["forward_host"],
                    "domain_names": proxy["domain_names"]
                }
                for proxy in proxy_hosts
            ]
            return result_dict
        else:
            return None

    def create_proxy_host(self, domain_names: List[str], forward_scheme: str, forward_host: str, forward_port: int, advanced_config: str) -> Union[dict, None]:
        """
        Create a new proxy host

        Args:
            domain_names (List[str]): List of domain names associated with the proxy host.
            forward_scheme (str): The scheme (HTTP or HTTPS) for forwarding traffic.
            forward_host (str): The target host to which traffic will be forwarded.
            forward_port (int): The port on the target host to which traffic will be forwarded.
            advanced_config (str): Advanced configuration options for the proxy host.

        Returns:
            dict or None: If the proxy host creation is successful,
            returns a dictionary containing information about the created proxy host with the following fields:
                - "proxy_id": The id of the created proxy host.
                - "forward_host": The target host name of the proxy.
                - "domain_names": A list of domain names associated with the proxy host.
            Returns None if the proxy host creation fails .
        """
        url = f"{self.base_url}/api/nginx/proxy-hosts"
        json = {
            "domain_names": domain_names,
            "forward_scheme": forward_scheme,
            "forward_host": forward_host,
            "forward_port": forward_port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": advanced_config,
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False,
            "locations": [],
        }
        headers = {
            'Content-Type': 'application/json',
            "Authorization": f"Bearer {self.api_token}"
        }
        response = requests.post(url, json=json, headers=headers)
        if response.status_code == 201:
            proxy_hosts = response.json()
            proxy_id = proxy_hosts.get("id")
            domain_names = proxy_hosts.get("domain_names")
            forward_host = proxy_hosts.get("forward_host")
            result_dict = {
                "proxy_id": proxy_id,
                "forward_host": forward_host,
                "domain_names": domain_names
            }
            return result_dict
        else:
            return None

    def update_proxy_host(self, proxy_id: int, domain_names: List[str], forward_scheme: str, forward_host: str, forward_port: int, advanced_config: str) -> Union[dict, None]:
        """
        Update an existing proxy host.

        Args:
            proxy_id (int): The ID of the proxy host to be updated.
            domain_names (List[str]): List of updated domain names associated with the proxy host.
            forward_scheme (str): The updated scheme (HTTP or HTTPS) for forwarding traffic.
            forward_host (str): The updated target host to which traffic will be forwarded.
            forward_port (int): The updated port on the target host to which traffic will be forwarded.
            advanced_config (str): Updated advanced configuration options for the proxy host.

        Returns:
            dict or None: If the proxy host update is successful,
            returns a dictionary containing information about the updated proxy host with the following fields:
                - "proxy_id": The ID of the updated proxy host.
                - "forward_host": The target host name of the proxy after the update.
                - "domain_names": A list of updated domain names associated with the proxy host.
            Returns None if the proxy host update fails.
        """
        url = f"{self.base_url}/api/nginx/proxy-hosts/{proxy_id}"
        headers = {
            'Content-Type': 'application/json',
            "Authorization": f"Bearer {self.api_token}"
        }
        json = {
            "domain_names": domain_names,
            "forward_scheme": forward_scheme,
            "forward_host": forward_host,
            "forward_port": forward_port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": advanced_config,
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False,
            "locations": [],
        }
        response = requests.put(url, json=json, headers=headers)
        if response.status_code == 200:
            proxy_hosts = response.json()
            proxy_id = proxy_hosts.get("id")
            domain_names = proxy_hosts.get("domain_names")
            forward_host = proxy_hosts.get("forward_host")
            result_dict = {
                "proxy_id": proxy_id,
                "forward_host": forward_host,
                "domain_names": domain_names
            }
            return result_dict
        else:
            return None

    def delete_proxy_host(self, proxy_id: int) -> Union[bool, None]:
        """
        Delete a proxy host

        Args:
            proxy_id (int): The ID of the proxy host to be deleted.

        Returns:
            bool or None: Returns the response object if the proxy host is successfully deleted ,
            indicating a successful deletion. Returns None if the deletion fails .           
        """
        url = f"{self.base_url}/api/nginx/proxy-hosts/{proxy_id}"
        headers = {
            'Content-Type': 'application/json',
            "Authorization": f"Bearer {self.api_token}"
        }
        response = requests.delete(url, headers=headers)
        if response.status_code == 200:
            return response
        return None
