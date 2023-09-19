import json

from src.core.apiHelper import APIHelper
from src.core.config import ConfigManager


class PortainerAPI:
    """
    This class is used to interact with Portainer API
    The Portainer API documentation can be found at: https://app.swaggerhub.com/apis/portainer/portainer-ce/2.19.0

    Attributes:
        api (APIHelper): API helper

    Methods:
        get_jwt_token(username: str, password: str) -> Response): Get JWT token
        get_endpoints() -> Response: Get endpoints
        get_stacks(endpointID: int) -> Response: Get stacks
        get_stack_by_id(stackID: int) -> Response: Get stack by ID
        remove_stack(stackID: int,endPointID: int) -> Response: Remove a stack
        create_stack_standlone_repository(app_name: str, endpointId: int,repositoryURL:str) -> Response: Create a stack from a standalone repository
        start_stack(stackID: int, endpointId: int) -> Response: Start a stack
        stop_stack(stackID: int, endpointId: int) -> Response: Stop a stack
        redeploy_stack(stackID: int, endpointId: int) -> Response: Redeploy a stack
    """

    def __init__(self):
        """
        Initialize the PortainerAPI instance
        """
        self.api = APIHelper(
            ConfigManager().get_value("portainer", "base_url"),
            {
                "Content-Type": "application/json",
            },
        )

    def set_jwt_token(self, jwt_token):
        """
        Set JWT token

        Args:
            jwt_token (str): JWT token
        """
        self.api.headers["Authorization"] = f"Bearer {jwt_token}"

    def get_jwt_token(self, username: str, password: str):
        """
        Get JWT token

        Args:
            username (str): Username
            password (str): Password

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path="auth",
            headers={"Content-Type": "application/json"},
            json={
                "password": password,
                "username": username,
            },
        )
       

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
    
    def get_endpoint_by_id(self, endpointID: int):
        """
        Get endpoint by ID

        Args:
            endpointID (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.get(path=f"endpoints/{endpointID}")

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

    def get_stacks(self, endpointID: int):
        """
        Get stacks

        Args:
            endpointID (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.get(
            path="stacks",
            params={
                "filters": json.dumps(
                    {"EndpointID": endpointID, "IncludeOrphanedStacks": True}
                )
            },
        )

    def get_stack_by_id(self, stackID: int):
        """
        Get stack by ID

        Args:
            stackID (int): Stack ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.get(path=f"stacks/{stackID}")

    def remove_stack(self, stackID: int, endPointID: int):
        """
        Remove a stack

        Args:
            stackID (int): Stack ID
            endPointID (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.delete(
            path=f"stacks/{stackID}", params={"endpointId": endPointID}
        )

    def create_stack_standlone_repository(self, stack_name: str, endpointId: int, repositoryURL: str):
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
            },
        )

    def start_stack(self, stackID: int, endpointId: int):
        """
        Start a stack

        Args:
            stackID (int): Stack ID
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path=f"stacks/{stackID}/start", params={"endpointId": endpointId}
        )

    def stop_stack(self, stackID: int, endpointId: int):
        """
        Stop a stack

        Args:
            stackID (int): Stack ID
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path=f"stacks/{stackID}/stop", params={"endpointId": endpointId}
        )

    def redeploy_stack(self, stackID: int, endpointId: int):
        """
        Redeploy a stack

        Args:
            stackID (int): Stack ID
            endpointId (int): Endpoint ID

        Returns:
            Response: Response from Portainer API
        """
        return self.api.post(
            path=f"stacks/{stackID}/redeploy", params={"endpointId": endpointId}
        )
