import json
from src.core.exception import CustomException
from src.external.portainer_api import PortainerAPI
from src.core.logger import logger


class PortainerManager:
    """
    Portainer Manager

    Attributes:
        portainer (PortainerAPI): Portainer API

    Methods:
        get_local_endpoint_id(): Get local endpoint id
        check_endpoint_exists(endpoint_id): Check endpoint exists
        check_stack_exists(stack_name, endpoint_id): Check stack exists
        create_stack_from_repository(stack_name, endpoint_id,repositoryURL,user_name,user_password): Create stack from repository
        get_stacks(endpoint_id): Get stacks
        get_stack_by_id(stack_id): Get stack by id
        get_stack_by_name(stack_name, endpoint_id): Get stack by name
        remove_stack(stack_id, endpoint_id): Remove stack by id
        remove_stack_and_volumes(stack_id, endpoint_id): Remove stack and volumes by id
        get_volumes_by_stack_name(stack_name, endpoint_id): Get volumes by stack name
        remove_volume(volume_names, endpoint_id): Remove volume by name
    """
    def __init__(self):
        try:
            self.portainer = PortainerAPI()
        except Exception as e:
            logger.error(f"Init Portainer API Error:{e}")
            raise CustomException()

    def get_local_endpoint_id(self):
        """
        Get local endpoint id: the endpoint id of the local docker engine
        if there are multiple local endpoints, return the one with the smallest id

        Returns:
            str: local endpoint id
        """
        # get all endpoints
        response = self.portainer.get_endpoints()
        if response.status_code == 200:
            endpoints = response.json()
            local_endpoint = None
            for endpoint in endpoints:
                # find the local endpoint
                if endpoint["URL"] == "unix:///var/run/docker.sock":
                    if local_endpoint is None: # if there is only one local endpoint, return it
                        local_endpoint = endpoint
                    elif endpoint["Id"] < local_endpoint["Id"]: # if there are multiple local endpoints, return the one with the smallest id
                        local_endpoint = endpoint
            if local_endpoint is not None: 
                return local_endpoint["Id"]
            else:
                logger.error(f"Get local endpoint id error: Local endpoint is not exist")
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details="Local endpoint is not exist"
                )
        else:
            logger.error(f"Get local endpoint id error: {response.status_code}:{response.text}")
            raise CustomException()

    def check_endpoint_exists(self, endpoint_id: int):
        """
        Check endpoint exists

        Args:
            endpoint_id (int): endpoint id

        Returns:
            bool: endpoint exists or not
        """
        response = self.portainer.get_endpoint_by_id(endpoint_id)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            logger.error(f"Check endpoint:{endpoint_id} exists error: {response.status_code}:{response.text}")
            raise CustomException()
        
    def check_stack_exists(self, stack_name: str, endpoint_id: int):
        """
        Check stack exists

        Args:
            stack_name (str): stack name
            endpoint_id (int): endpoint id

        Returns:
            bool: stack exists or not
        """
        # get all stacks
        response = self.portainer.get_stacks(endpoint_id)
        if response.status_code == 200:
            stacks = response.json()
            for stack in stacks:
                if stack["Name"] == stack_name:
                    return True
            return False
        else:
            logger.error(f"Check stack:{stack_name} exists error: {response.status_code}:{response.text}")
            raise CustomException()
        
    def create_stack_from_repository(self, stack_name: str, endpoint_id: int,repositoryURL : str,user_name:str,user_password:str):
        response = self.portainer.create_stack_standlone_repository(stack_name, endpoint_id,repositoryURL,user_name,user_password)
        if response.status_code == 200:
            return response.json()
        else:
            message = response.text
            if message:
                try:
                    response_details = json.loads(message)
                    message = response_details.get('details', 'unknown error')
                except json.JSONDecodeError:
                    pass 
            logger.error(f"Create stack:{stack_name} from repository:{repositoryURL} error: {response.status_code}:{response.text}")
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=message
            )
        
    def redeploy_stack(self, stack_id: int, endpoint_id: int,pull_image:bool,user_name:str,user_password:str):
        response = self.portainer.redeploy_stack(stack_id, endpoint_id,pull_image,user_name,user_password)
        if response.status_code == 200:
            return response.json()
        else:
            message = response.text
            if message:
                try:
                    response_details = json.loads(message)
                    message = response_details.get('details', 'unknown error')
                except json.JSONDecodeError:
                    pass 
            logger.error(f"Redeploy stack:{stack_id} error: {response.status_code}:{response.text}")
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=message
            )
    
    def get_stacks(self, endpoint_id: int):
        """
        Get stacks

        Args:
            endpoint_id (int): endpoint id

        Returns:
            list: stack list
        """
        response = self.portainer.get_stacks(endpoint_id)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Get stacks from endpoint:{endpoint_id} error: {response.status_code}:{response.text}")
            raise CustomException()
        
    def get_stack_by_id(self, stack_id: int):
        """
        Get stack by id

        Args:
            stack_id (int): stack id

        Returns:
            dict: stack info
        """
        response = self.portainer.get_stack_by_id(stack_id)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Get stack by id:{stack_id} error: {response.status_code}:{response.text}")
            raise CustomException()
        
    def get_stack_by_name(self, stack_name: str, endpoint_id: int):
        """
        Get stack by name

        Args:
            stack_name (str): stack name
            endpoint_id (int): endpoint id

        Returns:
            dict: stack info
        """
        response = self.portainer.get_stacks(endpoint_id)
        if response.status_code == 200:
            stacks = response.json()
            for stack in stacks:
                if stack["Name"] == stack_name:
                    return stack
            return None
        else:
            logger.error(f"Get stack by name:{stack_name} error: {response.status_code}:{response.text}")
            raise CustomException()
    
    def remove_stack(self, stack_id: int, endpoint_id: int):
        """
        Remove stack by id

        Args:
            stack_id (int): stack id
            endpoint_id (int): endpoint id
        """
        response = self.portainer.remove_stack(stack_id, endpoint_id)
        if response.status_code != 204:
            logger.error(f"Remove stack:{stack_id} error: {response.status_code}:{response.text}")
            raise CustomException()
    
    def remove_vloumes(self, stack_name: str, endpoint_id: int):
        """
        Remove volumes by stack name

        Args:
            stack_name (str): stack name
            endpoint_id (int): endpoint id
        """
        volumes = self.get_volumes_by_stack_name(stack_name, endpoint_id,True)
        if volumes is not None:
            volume_names = []
            for volume in volumes: 
                volume_names.append(volume["Name"])
            self.remove_volume(volume_names, endpoint_id)

    def remove_stack_and_volumes(self, stack_id: int, endpoint_id: int):
        """
        Remove stack and volumes by id

        Args:
            stack_id (int): stack id
            endpoint_id (int): endpoint id
        """
        # get stack name
        stack_name = self.get_stack_by_id(stack_id).get("Name") 

        # remove stack
        response = self.portainer.remove_stack(stack_id, endpoint_id)
        if response.status_code != 204:
            logger.error(f"Remove stack:{stack_id} error: {response.status_code}:{response.text}")
            raise CustomException()

        # remove volumes
        try: 
            if stack_name is not None:
                volumes = self.get_volumes_by_stack_name(stack_name, endpoint_id,True)
                volume_names = []
                for volume in volumes: 
                    volume_names.append(volume["Name"])

                if len(volume_names) > 0:
                    self.remove_volume(volume_names, endpoint_id)
        except (CustomException,Exception) as e:
            raise CustomException()

    def get_volumes_by_stack_name(self, stack_name: str, endpoint_id: int,dangling:bool):
        """
        Get volumes by stack name

        Args:
            stack_name (str): stack name
            endpoint_id (int): endpoint id
            dangling (bool): the volume is dangling or not

        Returns:
            dict: volumes info
        """
        response = self.portainer.get_volumes(endpoint_id,dangling)
        if response.status_code == 200:
            try:
                volumes = response.json().get("Volumes", [])
                # volumes_info = [volume for volume in volumes if volume.get("Labels", {}).get("com.docker.compose.project") == stack_name]
                volumes_info = [
                    volume for volume in volumes 
                    if (
                        isinstance(volume, dict) and 
                        volume.get("Labels") and 
                        volume.get("Labels", {}).get("com.docker.compose.project") == stack_name
                    )
                ]
            except Exception as e:
                logger.error(f"Get volumes by stack name:{stack_name} error: {e}")
                raise CustomException()
            return volumes_info
        else:
            logger.error(f"Get volumes by stack name:{stack_name} error: {response.status_code}:{response.text}")
            raise CustomException()

    def remove_volume(self, volume_names: list, endpoint_id: int):
        """
        Remove volume by name

        Args:
            volume_names (list): volume name list
            endpoint_id (int): endpoint id
        """
        for volume_name in volume_names:
            response = self.portainer.remove_volume_by_name(endpoint_id,volume_name)
            if response.status_code != 204:
                logger.error(f"Remove volume:{volume_name} error: {response.status_code}:{response.text}")
                raise CustomException()
            
    def up_stack(self, stack_id: int, endpoint_id: int):
        """
        Up stack by id

        Args:
            stack_id (int): stack id
            endpoint_id (int): endpoint id
        """
        response = self.portainer.up_stack(stack_id, endpoint_id)
        if response.status_code == 409:
            raise CustomException(400,"Invalid Request","The app is already running")
        elif response.status_code != 200:
            logger.error(f"Up stack:{stack_id} error: {response.status_code}:{response.text}")
            raise CustomException()
        
    def down_stack(self, stack_id: int, endpoint_id: int):
        """
        Down stack by id

        Args:
            stack_id (int): stack id
            endpoint_id (int): endpoint id
        """
        response = self.portainer.down_stack(stack_id, endpoint_id)
        if response.status_code == 400:
            raise CustomException(400,"Invalid Request","The app is already uninstalled")
        elif response.status_code != 200:
            logger.error(f"Down stack:{stack_id} error: {response.status_code}:{response.text}")
            raise CustomException()
    
    def stop_stack(self, stack_name: int, endpoint_id: int):
        """
        Stop stack by name

        Args:
            stack_name (int): stack name
            endpoint_id (int): endpoint id
        """
        containers_response = self.portainer.get_containers_by_stackName(endpoint_id,stack_name)
        if containers_response.status_code == 200:
            containers = containers_response.json()
            for container in containers:
                container_id = container.get("Id")
                stop_response = self.portainer.stop_container(endpoint_id,container_id)
                if stop_response.status_code in {304, 404}:
                    continue
                elif stop_response.status_code != 204:
                    message = stop_response.text
                    if message:
                        try:
                            response_details = json.loads(stop_response.text)
                            message = response_details.get('details', 'unknown error')
                        except json.JSONDecodeError:
                            pass 
                    logger.error(f"Stop container:{container_id} error: {stop_response.status_code}:{message}")
                    raise CustomException(
                        status_code=400,
                        message="Invalid Request",
                        details=message
                    )
        else:
            logger.error(f"Get containers by stack name:{stack_name} error: {containers_response.status_code}:{containers_response.text}")
            raise CustomException()

    def start_stack(self, stack_name: int, endpoint_id: int):
        """
        Start stack by name

        Args:
            stack_name (int): stack name
            endpoint_id (int): endpoint id
        """
        containers_response = self.portainer.get_containers_by_stackName(endpoint_id,stack_name)
        if containers_response.status_code == 200:
            containers = containers_response.json()
            for container in containers:
                container_id = container.get("Id")
                start_response=self.portainer.start_container(endpoint_id,container_id)
                if start_response.status_code in {304, 404}:
                    continue
                elif start_response.status_code != 204:
                    message = start_response.text
                    if message:
                        try:
                            response_details = json.loads(start_response.text)
                            message = response_details.get('details', 'unknown error')
                        except json.JSONDecodeError:
                            pass 
                    logger.error(f"Start container:{container_id} error: {start_response.status_code}:{message}")
                    raise CustomException(
                        status_code=400,
                        message="Invalid Request",
                        details=message
                    )
        else:
            logger.error(f"Get containers by stack name:{stack_name} error: {containers_response.status_code}:{containers_response.text}")
            raise CustomException()

    def restart_stack(self, stack_name: int, endpoint_id: int):
        """
        Restart stack by name

        Args:
            stack_name (int): stack name
            endpoint_id (int): endpoint id
        """
        containers_response = self.portainer.get_containers_by_stackName(endpoint_id,stack_name)
        if containers_response.status_code == 200:
            containers = containers_response.json()
            for container in containers:
                container_id = container.get("Id")
                restart_response=self.portainer.restart_container(endpoint_id,container_id)
                if restart_response.status_code != 204:
                    message = restart_response.text
                    if message:
                        try:
                            response_details = json.loads(restart_response.text)
                            message = response_details.get('details', 'unknown error')
                        except json.JSONDecodeError:
                            pass 
                    logger.error(f"Restart container:{container_id} error: {restart_response.status_code}:{message}")
                    raise CustomException(
                        status_code=400,
                        message="Invalid Request",
                        details=message
                    )
        else:
            logger.error(f"Get containers by stack name:{stack_name} error: {containers_response.status_code}:{containers_response.text}")
            raise CustomException()

    def get_containers(self, endpoint_id: int):
        """
        Get containers

        Args:
            endpoint_id (int): endpoint id

        Returns:
            list: containers info
        """
        response = self.portainer.get_containers(endpoint_id)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Get containers from endpoint:{endpoint_id} error: {response.status_code}:{response.text}")
            raise CustomException()

    def get_containers_by_stack_name(self, stack_name: str, endpoint_id: int):
        """
        Get containers by stack name

        Args:
            stack_name (str): stack name
            endpoint_id (int): endpoint id

        Returns:
            list: containers info
        """
        response = self.portainer.get_containers_by_stackName(endpoint_id,stack_name)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Get containers by stack name:{stack_name} error: {response.status_code}:{response.text}")
            raise CustomException()
        
    def get_container_by_id(self, endpoint_id: int, container_id: str):
        """
        Get container by id

        Args:
            endpoint_id (int): endpoint id
            container_id (str): container id

        Returns:
            dict: container info
        """
        response = self.portainer.get_container_by_id(endpoint_id, container_id)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Get container by id:{container_id} error: {response.status_code}:{response.text}")
            raise CustomException()