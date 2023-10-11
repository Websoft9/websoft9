import requests

from src.core.logger import logger

class APIHelper:
    """
    Helper class for making API calls

    Attributes:
        base_url (str): Base URL for API
        headers (dict): Headers

    Methods:
        get(path: str, params: dict = None, headers: dict = None) -> Response: Get a resource
        post(path: str, params: dict = None, json: dict = None, headers: dict = None) -> Response: Create a resource
        put(path: str, params: dict = None, json: dict = None, headers: dict = None) -> Response: Update a resource
        delete(path: str, headers: dict = None) -> Response: Delete a resource
    """
    def __init__(self, base_url, headers=None):
        """
        Initialize the APIHelper instance.

        Args:
            base_url (str): Base URL for API
            headers (dict): Headers
        """
        self.base_url = base_url
        self.headers = headers

    def get(self, path, params=None, headers=None):
        """
        Get a resource

        Args:
            path (str): Path to resource
            params (dict): Query parameters
            headers (dict): Headers

        Returns:
            Response: Response from API
        """
        url = f"{self.base_url}/{path}"
        return requests.get(url, params=params, headers=self._merge_headers(headers))

    def post(self, path, params=None, json=None, headers=None):
        """
        Create a resource

        Args:
            path (str): Path to resource
            params (dict): Query parameters
            json (dict): JSON payload
            headers (dict): Headers

        Returns:
            Response: Response from API
        """
        url = f"{self.base_url}/{path}"
        return requests.post(url, params=params, json=json, headers=self._merge_headers(headers))

    def put(self, path, params=None, json=None, headers=None):
        """
        Update a resource

        Args:
            path (str): Path to resource
            params (dict): Query parameters
            json (dict): JSON payload
            headers (dict): Headers
        
        Returns:
            Response: Response from API
        """
        url = f"{self.base_url}/{path}"
        return requests.put(url, params=params, json=json, headers=self._merge_headers(headers))

    def delete(self, path,params=None, headers=None):
        """
        Delete a resource

        Args:
            path (str): Path to resource
            headers (dict): Headers
        
        Returns:
            Response: Response from API
        """
        url = f"{self.base_url}/{path}"
        return  requests.delete(url, params=params, headers=self._merge_headers(headers))

    def _merge_headers(self, headers):
        """
        Merge the headers passed in with the headers set on the APIHelper instance.

        Args:
            headers (dict): Headers to merge

        Returns:
            dict: Merged headers
        """
        if self.headers and headers:
            return {**self.headers, **headers}
        return self.headers or headers