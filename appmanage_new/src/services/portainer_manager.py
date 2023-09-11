from fastapi import logger

from src.external.portainer_api import PortainerAPI


class PortainerManager:
    def __init__(self, portainer_url, portainer_username, portainer_password): 
        """
        Init Portainer Manager
        Args:
            portainer_url (str): The url of the portainer
            portainer_username (str): The username of the portainer
            portainer_password (str): The password of the portainer
        """
        self.portainer_url = portainer_url
        self.portainer_username = portainer_username
        self.portainer_password = portainer_password
        try:
            self.portainer = PortainerAPI(self.portainer_url)
            self._init_portainer_token()
        except Exception as e:
            logger.error(f"Init Portainer API Error:{e}")
            raise e