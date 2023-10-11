import requests

from src.core.config import ConfigManager

class PublicIPGetter:
    """
    A utility class to retrieve a valid IPv4 address.

    Attributes:
        url_list (list[str]): A list of URLs to retrieve the response from.

    Methods:
        get_ip_address(): Retrieves and returns a valid IPv4 address.
    """

    def __init__(self):
        """
        Initializes the PublicIPGetter class.
        """
        self.url_list = [url.strip() for url in ConfigManager().get_value("public_ip_url_list", "url_list").split(',')]

    def get_ip_address(self):
        """
        Retrieves and returns a valid IPv4 address from the list of URLs.

        Returns:
            str: The valid IPv4 address if found, otherwise None.
        """
        for url in self.url_list:
            ip = self._get_ip(url)
            if ip and self._is_valid_ipv4(ip):
                return ip
        return None

    def _get_ip(self, url):
        """
        Retrieves and returns the response from the given URL.

        Args: 
            url (str): The URL to retrieve the response from.

        Returns:
            str: The response from the given URL if found, otherwise None.
        """
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return response.text.strip()
        except requests.RequestException:
            pass
        return None

    def _is_valid_ipv4(self, ip) -> bool:
        """
        Checks if the given string is a valid IPv4 address.

        Args:
            ip (str): The string to check.

        Returns:
            bool: True if the string is a valid IPv4 address, otherwise False.
        """
        parts = ip.split('.')
        return len(parts) == 4 and all(0 <= int(part) < 256 for part in parts)
    
if __name__ == "__main__":
    ip = PublicIPGetter().get_ip_address()
    print(ip)
