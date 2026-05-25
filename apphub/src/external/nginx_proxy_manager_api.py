from typing import List
import os
import socket
from urllib.parse import urlparse

from src.core.apiHelper import APIHelper
from src.core.config import ConfigManager
from src.core.logger import logger


def resolve_nginx_proxy_manager_api_base_url() -> str:
    fallback = os.getenv("WEBSOFT9_NGINX_PROXY_MANAGER_API_BASE_URL", "http://127.0.0.1:81/api").rstrip("/")

    try:
        configured = (ConfigManager().get_value("nginx_proxy_manager", "base_url") or "").rstrip("/")
    except Exception:
        return fallback

    if not configured:
        return fallback

    parsed = urlparse(configured)
    host = parsed.hostname
    if not parsed.scheme or not parsed.netloc or not host:
        return fallback

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        logger.error(f"Nginx Proxy Manager base_url host '{host}' is unreachable; falling back to {fallback}")
        return fallback

    return configured


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
            resolve_nginx_proxy_manager_api_base_url(),
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
        certificate_id: int | None = None,
        ssl_forced: bool = False,
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
                "certificate_id": certificate_id or 0,
                "meta": {"letsencrypt_agree": False, "dns_challenge": False},
                "advanced_config": advanced_config,
                "block_exploits": False,
                "caching_enabled": False,
                "allow_websocket_upgrade": False,
                "http2_support": False,
                "hsts_enabled": False,
                "hsts_subdomains": False,
                "ssl_forced": ssl_forced,
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

    def get_certificates(self):
        """
        get all certificates

        Returns:
            Response: Response from Nginx Proxy Manager API
        """
        return self.api.get(
            path="nginx/certificates", params={"expand": "owner,proxy_hosts,dead_hosts,redirection_hosts"}
        )

    def create_certificate(self, domain_names: List[str], email: str):
        """
        Request a Let's Encrypt certificate.

        Args:
            domain_names (List[str]): Domain names to include in the certificate
            email (str): Let's Encrypt account email

        Returns:
            Response: Response from Nginx Proxy Manager API
        """
        return self.api.post(
            path="nginx/certificates",
            json={
                "provider": "letsencrypt",
                "domain_names": domain_names,
                "meta": {
                    "letsencrypt_email": email,
                    "letsencrypt_agree": True,
                },
            },
        )

    def create_custom_certificate(self, nice_name: str, certificate_pem: str, key_pem: str):
        """
        Upload a custom (non-Let's Encrypt) SSL certificate.

        Args:
            nice_name (str): Display name for the certificate
            certificate_pem (str): PEM-encoded certificate content
            key_pem (str): PEM-encoded private key content

        Returns:
            Response: Response from Nginx Proxy Manager API
        """
        return self.api.post(
            path="nginx/certificates",
            json={
                "provider": "other",
                "nice_name": nice_name,
                "meta": {
                    "certificate": certificate_pem,
                    "certificate_key": key_pem,
                },
            },
        )