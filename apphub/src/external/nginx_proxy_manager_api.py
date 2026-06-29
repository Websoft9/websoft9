from typing import List
import os
import socket
from urllib.parse import urlparse

import requests

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

    def create_certificate(self, domain_names: List[str], email: str, nice_name: str | None = None):
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
                "nice_name": nice_name or (domain_names[0] if domain_names else email),
                "domain_names": domain_names,
                "meta": {
                    "letsencrypt_email": email,
                    "letsencrypt_agree": True,
                    "dns_challenge": False,
                },
            },
        )

    def create_custom_certificate(self, nice_name: str, certificate_pem: str, key_pem: str):
        """
        Upload a custom (non-Let's Encrypt) SSL certificate.

        NPM requires a two-step flow for custom certificates:
        1. Create a certificate shell (provider + nice_name only)
        2. Upload the PEM files so NPM can parse and store the real expires_on

        Args:
            nice_name (str): Display name for the certificate
            certificate_pem (str): PEM-encoded certificate content
            key_pem (str): PEM-encoded private key content

        Returns:
            Response: Response from Nginx Proxy Manager API (the final certificate with correct expires_on)
        """
        # Step 1: Create certificate shell
        create_resp = self.api.post(
            path="nginx/certificates",
            json={
                "provider": "other",
                "nice_name": nice_name,
            },
        )
        if create_resp.status_code not in [200, 201]:
            return create_resp

        certificate = create_resp.json()
        cert_id = certificate.get("id")
        if not cert_id:
            return create_resp

        # Step 2: Upload certificate files so NPM parses them and updates expires_on
        base_url = self.api.base_url
        url = f"{base_url}/nginx/certificates/{cert_id}/upload"
        merged_headers = dict(self.api.headers)
        merged_headers.pop("Content-Type", None)  # Let requests set the multipart boundary

        try:
            upload_resp = requests.post(
                url,
                files={
                    "certificate": ("certificate.pem", certificate_pem, "application/x-pem-file"),
                    "certificate_key": ("certificate_key.pem", key_pem, "application/x-pem-file"),
                },
                headers=merged_headers,
                verify=self.api.verify,
            )
        except requests.RequestException as exc:
            logger.error(f"Certificate file upload failed: {exc}")
            # Return the create response as fallback; the caller can still use the cert shell
            return create_resp

        if upload_resp.status_code not in [200, 201]:
            logger.error(
                f"NPM upload returned {upload_resp.status_code}: {upload_resp.text[:500]}"
            )
            return create_resp

        # Step 3: Fetch the updated certificate to get the real expires_on
        get_resp = self.api.get(
            path=f"nginx/certificates/{cert_id}",
            params={"expand": "owner,proxy_hosts,dead_hosts,redirection_hosts"},
        )
        if get_resp.status_code == 200:
            # Patch the response so downstream code sees a proper status code
            get_resp.status_code = create_resp.status_code
            return get_resp

        return create_resp