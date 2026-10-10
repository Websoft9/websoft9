from datetime import datetime
import json
import os
import socket
import threading
import time
from typing import Optional
from urllib.parse import urlparse

import requests

from src.core.apiHelper import APIHelper
from src.core.config import ConfigManager
from functools import wraps
from src.core.logger import logger
from src.core.exception import CustomException
from src.services.integration_credentials import IntegrationCredentialProvider


def resolve_portainer_api_base_url() -> str:
    fallback = os.getenv("WEBSOFT9_PORTAINER_API_BASE_URL", "http://127.0.0.1:9004/api").rstrip("/")

    try:
        configured = (ConfigManager().get_value("portainer", "base_url") or "").rstrip("/")
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
        logger.error(f"Portainer base_url host '{host}' is unreachable; falling back to {fallback}")
        return fallback

    return configured


class JWTManager:
    jwt_token = None
    token_lock = threading.Lock()

    @classmethod
    def get_token(cls):
        with cls.token_lock:
            if cls.jwt_token is None:
                cls.refresh_token()
            return cls.jwt_token

    @classmethod
    def refresh_token(cls):
        credentials = IntegrationCredentialProvider().get_portainer_credentials()
        username = credentials.username
        password = credentials.password
        api = APIHelper(
            resolve_portainer_api_base_url(),
            {
                "Content-Type": "application/json",
            },
            verify=False,
        )
        token_response = api.post(
            path="auth",
            json={
                "username": username,
                "password": password,
            },
        )
        if token_response.status_code == 200:
            cls.jwt_token = token_response.json()['jwt']
        else:
            logger.error(f"Error Calling Portainer API: {token_response.status_code}:{token_response.text}")
            raise CustomException()


class PortainerAPI:
    """
    This class is used to interact with Portainer API
    The Portainer API documentation can be found at: https://app.swaggerhub.com/apis/portainer/portainer-ce/2.19.0

    Attributes:
        api (APIHelper): API helper

    Methods:
        set_jwt_token(jwt_token): Set JWT token
        get_jwt_token(username, password): Get JWT token
        get_endpoints(): Get endpoints  
        get_endpoint_by_id(endpointId): Get endpoint by ID
        create_endpoint(name, EndpointCreationType): Create an endpoint
        get_stacks(endpointId): Get stacks
        get_stack_by_id(stackID): Get stack by ID
        remove_stack(stackID, endpointId): Remove a stack
        create_stack_standlone_repository(stack_name, endpointId, repositoryURL): Create a stack from a standalone repository
        start_stack(stackID, endpointId): Start a stack
        stop_stack(stackID, endpointId): Stop a stack
        redeploy_stack(stackID, endpointId): Redeploy a stack
        get_volumes(endpointId,dangling): Get volumes in endpoint
        remove_volume_by_name(endpointId,volume_name): Remove volumes by name
    """

    jwt_token = None

    def __init__(self):
        """
        Initialize the PortainerAPI instance
        """
        self.api = APIHelper(
            resolve_portainer_api_base_url(),
            {
                "Content-Type": "application/json",
                # "Authorization": f"Bearer {JWTManager.get_token()}",
            },
            verify=False,
        )

    def auto_refresh_token(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self.api.headers["Authorization"] = f"Bearer {JWTManager.get_token()}"
            response = func(self, *args, **kwargs)
            if response.status_code == 401:  # If Unauthorized
                JWTManager.refresh_token()  # Refresh the token
                self.api.headers["Authorization"] = f"Bearer {JWTManager.get_token()}"
                response = func(self, *args, **kwargs)  # Retry the request
            # response.raise_for_status()  # This will raise an exception if the response contains an HTTP error status after retrying.
            return response
        return wrapper


    @auto_refresh_token
    def get_endpoints(self,start: int = 0,limit: int = 1000):
        """
        Get endpoints

        Returns:
            Response: Response from Portainer API
        """
        return self.api.get(
            path="endpoints",
            params={
                "start": start,
                "limit": limit,
            },
        )
    
    @auto_refresh_token
    def get_endpoint_by_id(self, endpointId: int):
        """
        Get endpoint by ID

        Args:
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.get(path=f"endpoints/{endpointId}")

    @auto_refresh_token
    def create_endpoint(self, name: str, EndpointCreationType: int = 1):
        """
        Create an endpoint

        Args:
            name (str): Endpoint name
            EndpointCreationType (int, optional): Endpoint creation type:
            1 (Local Docker environment), 2 (Agent environment), 3 (Azure environment), 4 (Edge agent environment) or 5 (Local Kubernetes Environment) ,Defaults to 1.

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path="endpoints",
            params={"Name": name, "EndpointCreationType": EndpointCreationType},
        )

    @auto_refresh_token
    def get_stacks(self, endpointId: int):
        """
        Get stacks

        Args:
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.get(
            path="stacks",
            params={
                "filters": json.dumps(
                    {"EndpointID": endpointId, "IncludeOrphanedStacks": True}
                )
            },
        )

    @auto_refresh_token
    def get_stack_by_id(self, stackID: int):
        """
        Get stack by ID

        Args:
            stackID (int): Stack ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.get(path=f"stacks/{stackID}")

    @auto_refresh_token
    def remove_stack(self, stackID: int, endpointId: int):
        """
        Remove a stack

        Args:
            stackID (int): Stack ID
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.delete(
            path=f"stacks/{stackID}", params={"endpointId": endpointId}
        )

    @auto_refresh_token
    def create_stack_standlone_repository(self, stack_name: str, endpointId: int, repositoryURL: str,usr_name:str,usr_password:str):
        """
        Create a stack from a standalone repository

        Args:
            stack_name (str): Stack name
            endpointId (int): Endpoint ID
            repositoryURL (str): Repository URL

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path="stacks/create/standalone/repository",
            params={"endpointId": endpointId},
            json={
                "Name": stack_name,
                "RepositoryURL": repositoryURL,
                "ComposeFile": "docker-compose.yml",
                "repositoryAuthentication": True,
                "RepositoryUsername": usr_name,
                "RepositoryPassword": usr_password,
                "env":[{
                    "name": "DEPLOY_TIME",
                    "value": datetime.now().strftime("%Y%m%d%H%M%S")
                }]
            },
        )

    @auto_refresh_token
    def up_stack(self, stackID: int, endpointId: int):
        """
        Up a stack

        Args:
            stackID (int): Stack ID
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path=f"stacks/{stackID}/start", params={"endpointId": endpointId}
        )

    @auto_refresh_token
    def down_stack(self, stackID: int, endpointId: int):
        """
        Down a stack

        Args:
            stackID (int): Stack ID
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path=f"stacks/{stackID}/stop", params={"endpointId": endpointId}
        )

    @auto_refresh_token
    def update_stack_git(
        self,
        stackID: int,
        endpointId: int,
        repositoryURL: str,
        repositoryReferenceName: str,
        configFilePath: str,
        repositoryAuthentication: bool,
        repositoryUsername: str,
        repositoryPassword: str,
        tlsSkipVerify: bool,
        env: Optional[list] = None,
        additionalFiles: Optional[list] = None,
        prune: bool = False,
        autoUpdate: Optional[dict] = None,
    ):
        return self.api.post(
            path=f"stacks/{stackID}/git",
            params={"endpointId": endpointId},
            json={
                "AutoUpdate": autoUpdate,
                "Env": env or [],
                "Prune": prune,
                "ConfigFilePath": configFilePath,
                "AdditionalFiles": additionalFiles or [],
                "RepositoryReferenceName": repositoryReferenceName,
                "RepositoryURL": repositoryURL,
                "RepositoryAuthentication": repositoryAuthentication,
                "RepositoryUsername": repositoryUsername,
                "RepositoryPassword": repositoryPassword,
                "TLSSkipVerify": tlsSkipVerify,
            },
        )

    @auto_refresh_token
    def get_volumes(self, endpointId: int,dangling: bool):
        """
        Get volumes in endpoint

        Args:
            endpointId (int): Endpoint ID
            dangling (bool): the volume is dangling or not
        """
        return self.api.get(
        path=f"endpoints/{endpointId}/docker/volumes",
        params={
            "filters": json.dumps(
                {"dangling": [str(dangling).lower()]}
            )
        }
    )
    
    @auto_refresh_token
    def remove_volume_by_name(self, endpointId: int,volume_name:str):
        """
        Remove volumes by name

        Args:
            endpointId (int): Endpoint ID
            volume_name (str): volume name
        """
        return self.api.delete(
        path=f"endpoints/{endpointId}/docker/volumes/{volume_name}",
    )

    @auto_refresh_token
    def get_containers(self, endpointId: int):
        """
        Get containers in endpoint

        Args:
            endpointId (int): Endpoint ID
        """
        return self.api.get(
            path=f"endpoints/{endpointId}/docker/containers/json",
            params={
                "all": True,
            }
        )

    @auto_refresh_token
    def get_containers_by_stackName(self, endpointId: int,stack_name:str):
        """
        Get containers in endpoint

        Args:
            endpointId (int): Endpoint ID
        """
        return self.api.get(
            path=f"endpoints/{endpointId}/docker/containers/json",
            params={
                "all": True,
                "filters": json.dumps(
                    {"label": [f"com.docker.compose.project={stack_name}"]}
                )
            }
        )

    @auto_refresh_token
    def get_container_by_id(self, endpointId: int, container_id: str):
        """
        Get container by ID

        Args:
            endpointId (int): Endpoint ID
            container_id (str): container ID
        """
        return self.api.get(
            path=f"endpoints/{endpointId}/docker/containers/{container_id}/json",
        )

    @auto_refresh_token
    def _container_output_response(self, endpoint_id: int, container_id: str, resource: str, params: dict):
        return requests.get(
            f"{self.api.base_url}/endpoints/{endpoint_id}/docker/containers/{container_id}/{resource}",
            params=params,
            headers={**self.api.headers, "Accept": "application/octet-stream"},
            verify=self.api.verify,
            stream=True,
            timeout=(5, 20),
        )

    def read_container_output(self, endpoint_id: int, container_id: str, resource: str, params: dict, max_bytes: int) -> bytes | None:
        if resource not in {"archive", "logs"}:
            raise ValueError("Unsupported container output")
        deadline = time.monotonic() + 20
        with self._container_output_response(endpoint_id, container_id, resource, params) as response:
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                raise RuntimeError("Container output unavailable")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                if time.monotonic() > deadline:
                    raise TimeoutError("Container output timed out")
                if len(content) + len(chunk) > max_bytes:
                    raise OverflowError("Container output too large")
                content.extend(chunk)
            return bytes(content)

    @auto_refresh_token
    def create_container_exec(self, endpoint_id: int, container_id: str, command: list[str]):
        return self.api.post(
            path=f"endpoints/{endpoint_id}/docker/containers/{container_id}/exec",
            json={"AttachStdout": True, "AttachStderr": True, "AttachStdin": False, "Tty": True, "Cmd": command},
        )

    def run_container_command(self, endpoint_id: int, container_id: str, command: list[str], max_bytes: int, timeout: int = 20) -> str:
        import websocket

        if not command or any(not isinstance(part, str) or not part or "\x00" in part for part in command):
            raise ValueError("Invalid container command")
        response = self.create_container_exec(endpoint_id, container_id, command)
        if response.status_code != 201:
            raise RuntimeError("Container command could not be created")
        exec_id = response.json().get("Id")
        if not isinstance(exec_id, str) or not exec_id:
            raise RuntimeError("Container command response is invalid")

        parsed = urlparse(self.api.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        url = f"{scheme}://{parsed.netloc}{parsed.path}/websocket/exec?endpointId={endpoint_id}&id={exec_id}"
        headers = {"Authorization": f"Bearer {JWTManager.get_token()}"}
        ssl_options = {"cert_reqs": 0} if not self.api.verify and scheme == "wss" else None
        socket = websocket.create_connection(url, header=headers, timeout=timeout, sslopt=ssl_options)
        output = bytearray()
        deadline = time.monotonic() + timeout
        try:
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError("Container command timed out")
                try:
                    chunk = socket.recv()
                except websocket.WebSocketConnectionClosedException:
                    break
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                if len(output) + len(chunk) > max_bytes:
                    raise OverflowError("Container command output too large")
                output.extend(chunk)
        finally:
            socket.close()
        return output.decode("utf-8", errors="replace")

    @auto_refresh_token
    def stop_container(self, endpointId: int, container_id: str):
        """
        Stop container

        Args:
            endpointId (int): Endpoint ID
            container_id (str): container ID
        """
        return self.api.post(
            path=f"endpoints/{endpointId}/docker/containers/{container_id}/stop",
        )
    
    @auto_refresh_token
    def start_container(self, endpointId: int, container_id: str):
        """
        Start container

        Args:
            endpointId (int): Endpoint ID
            container_id (str): container ID
        """
        return self.api.post(
            path=f"endpoints/{endpointId}/docker/containers/{container_id}/start",
        )
    
    @auto_refresh_token
    def restart_container(self, endpointId: int, container_id: str):
        """
        Restart container

        Args:
            endpointId (int): Endpoint ID
            container_id (str): container ID
        """
        return self.api.post(
            path=f"endpoints/{endpointId}/docker/containers/{container_id}/restart",
        )
    
    @auto_refresh_token
    def redeploy_stack(self, stackID: int, endpointId: int,pullImage:bool,user_name:str,user_password:str ):
        return self.api.put(
            path=f"stacks/{stackID}/git/redeploy", 
            params={"endpointId": endpointId},
            json={
                "env":[{
                    "name": "DEPLOY_TIME",
                    "value": "-"+datetime.now().strftime("%Y%m%d%H%M%S")
                }],
                "prune":False,
                "RepositoryReferenceName":"",
                "RepositoryAuthentication":True,
                "RepositoryUsername":user_name,
                "RepositoryPassword":user_password,
                "PullImage":pullImage
            }
        )