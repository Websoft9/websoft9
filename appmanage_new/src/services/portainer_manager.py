import json
import time
import jwt
import keyring
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.external.portainer_api import PortainerAPI
from src.core.logger import logger


class PortainerManager:
    def __init__(self):
        try:
            self.portainer = PortainerAPI()
            self._set_portainer_token()
        except Exception as e:
            logger.error(f"Init Portainer API Error:{e}")
            raise CustomException()

    def _set_portainer_token(self):
        service_name = "portainer"
        token_name = "user_token"

        # Try to get token from keyring
        try:
            jwt_token = keyring.get_password(service_name, token_name)
        except Exception as e:
            jwt_token = None

        # if the token is got from keyring,vaildate the exp time
        if jwt_token is not None:
            try:
                decoded_jwt = jwt.decode(jwt_token, options={"verify_signature": False})
                exp_timestamp = decoded_jwt['exp']
                # if the token is not expired, return it
                if int(exp_timestamp) - int(time.time()) > 3600:
                    self.portainer.set_jwt_token(jwt_token)
                    return
            except Exception as e:
                logger.error(f"Decode Portainer's Token Error:{e}")
                raise CustomException()

        # if the token is expired or not got from keyring, get a new one
        try:
            userName = ConfigManager().get_value("portainer", "user_name")
            userPwd = ConfigManager().get_value("portainer", "user_pwd")
        except Exception as e:
            logger.error(f"Get Portainer's UserName and UserPwd Error:{e}")
            raise CustomException()
        
        token_response = self.portainer.get_jwt_token(userName, userPwd)
        if token_response.status_code == 200:
            jwt_token = token_response.json()["jwt"]
            self.portainer.set_jwt_token(jwt_token)
             # set new token to keyring
            try:
                keyring.set_password(service_name, token_name, jwt_token)
            except Exception as e:
                logger.error(f"Set Portainer's Token To Keyring Error:{e}")
                raise CustomException()
        else:
            logger.error(f"Error Calling Portainer API: {token_response.status_code}:{token_response.text}")
            raise CustomException()
    
    def get_local_endpoint_id(self):
        """
        Get local endpoint id: the endpoint id of the local docker engine
        if there are multiple local endpoints, return the one with the smallest id

        Returns:
            str: local endpoint id
        """
        response = self.portainer.get_endpoints()
        if response.status_code == 200:
            endpoints = response.json()
            local_endpoint = None
            for endpoint in endpoints:
                if endpoint["URL"] == "unix:///var/run/docker.sock":
                    if local_endpoint is None:
                        local_endpoint = endpoint
                    elif endpoint["Id"] < local_endpoint["Id"]:
                        local_endpoint = endpoint
            if local_endpoint is not None:
                return local_endpoint["Id"]
            else:
                logger.error(f"Error get local endpoint id from portainer: {response.text}")
                raise CustomException()
        else:
            logger.error(f"Error get local endpoint id from portainer: {response.text}")
            raise CustomException()

    def check_endpoint_exists(self, endpoint_id: int):
        response = self.portainer.get_endpoint_by_id(endpoint_id)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            logger.error(f"Error validate endpoint is exist from portainer: {response.text}")
            raise CustomException()
        
    def check_stack_exists(self, stack_name: str, endpoint_id: int):
        response = self.portainer.get_stacks(endpoint_id)
        if response.status_code == 200:
            stacks = response.json()
            for stack in stacks:
                if stack["Name"] == stack_name:
                    return True
            return False
        else:
            logger.error(f"Error validate stack is exist from portainer: {response.text}")
            raise CustomException()
        
    def create_stack_from_repository(self, stack_name: str, endpoint_id: int,repositoryURL : str,user_name:str,user_password:str):
        response = self.portainer.create_stack_standlone_repository(stack_name, endpoint_id,repositoryURL,user_name,user_password)
        if response.status_code != 200:
            logger.error(f"Error create stack from portainer: {response.text}")
            raise CustomException()
        
    def get_stacks(self, endpoint_id: int):
        response = self.portainer.get_stacks(endpoint_id)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error get stacks from portainer: {response.text}")
            raise CustomException()
        
    def get_stack_by_id(self, stack_id: int):
        response = self.portainer.get_stack_by_id(stack_id)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error get stack by id from portainer: {response.text}")
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
            logger.error(f"Error get stack by name from portainer: {response.text}")
            raise CustomException()
    
    def remove_stack(self, stack_id: int, endpoint_id: int):
        response = self.portainer.remove_stack(stack_id, endpoint_id)
        if response.status_code != 204:
            logger.error(f"Error remove stack from portainer: {response.text}")
            raise CustomException()
    
    def remove_stack_and_volumes(self, stack_id: int, endpoint_id: int):
        # get stack name
        stack_name = self.get_stack_by_id(stack_id).get("Name") 

        # remove stack
        response = self.portainer.remove_stack(stack_id, endpoint_id)
        if response.status_code != 204:
            logger.error(f"Error remove stack from portainer: {response.text}")
            raise CustomException()
        
        # remove volumes
        try: 
            if stack_name is not None:
                volumes = self.get_volumes_by_stack_name(stack_name, endpoint_id,True) 
                volume_names = []
                for volume in volumes.get("mountpoint", []): 
                    volume_names.append(volume["name"])
                self.remove_volume(volume_names, endpoint_id) 
        except (CustomException,Exception) as e:
            raise CustomException()


    def get_volumes_by_stack_name(self, stack_name: str, endpoint_id: int,dangling:bool):
        """
        Get volumes by stack name

        Args:
            stack_name (str): stack name
            endpoint_id (int): endpoint id

        Returns:
            dict: volumes info
        """
        response = self.portainer.get_volumes(endpoint_id,dangling)
        if response.status_code == 200:
            volumes = response.json().get("Volumes", [])
            mountpoints = []
            
            for volume in volumes:
                labels = volume.get("Labels", {})
                
                if labels.get("com.docker.compose.project") == stack_name:
                    mountpoint_info = {
                        "name": volume["Name"],
                        "path": volume["Mountpoint"]
                    }
                    
                    mountpoints.append(mountpoint_info)
                    
            return {
                "stack_name": stack_name,
                "mountpoint": mountpoints
            }
        else:
            logger.error(f"Error remove stack from portainer: {response.text}")
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
                logger.error(f"Error remove volume from portainer: {response.text}")
                raise CustomException()