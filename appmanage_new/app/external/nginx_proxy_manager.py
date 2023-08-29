import requests

class NginxProxyManagerAPI:
    """
    This class provides methods to interact with the Nginx Proxy Manager API.

    Args:
        base_url (str): The base URL of the Nginx Proxy Manager API.
        api_token (str): The API Token to use for authorization.

    Attributes:
        base_url (str): The base URL of the Nginx Proxy Manager API.
        api_token (str): The API Token to use for authorization.

    Methods:
        get_token(identity, scope, secret): Request a new access token from Nginx Proxy Manager
        refresh_token(): Refresh your access token
    """

    def __init__(self, base_url, api_token):
        """
        Initialize the NginxProxyManagerAPI instance.

        Args:
            base_url (str): The base URL of the Nginx Proxy Manager API.
            api_token (str): The API token to use for authorization.
        """
        self.base_url = base_url
        self.api_token = api_token

    def get_token(self,identity,scope,secret):
        """
        Request a new access token from Nginx Proxy Manager

        Args:
            identity (string): user account with an email address
            scope (user): "user"
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
        data = {
            "identity": identity,
            "scope": scope,
            "secret": secret
        }
        response = requests.post(url,json=data, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def refresh_token(self):
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
         headers = {"Authorization": f"Bearer {self.api_token}"}
         response = requests.get(url, headers=headers)
         if response.status_code == 200:
            return response.json()
        else:
            return None