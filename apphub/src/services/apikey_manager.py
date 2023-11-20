import secrets
import hashlib
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger

class APIKeyManager:
    """
    A class for managing API keys.

    Methods:
        generate_key: Generate a new API key.
        delete_key: Delete the API key.
        get_key: Get the API key.
    """
    def generate_key(self):
        """
        Generate a new API key.
        """
        try:
            # Generate a random string
            base = secrets.token_urlsafe(32)
            # Hash the string
            key = hashlib.sha256(base.encode()).hexdigest()
            # Save the key
            ConfigManager().set_value('api_key', 'key', key)
            return key
        except Exception as e:
            logger.error("Error generating API key"+str(e))
            raise CustomException()

    def get_key(self):
        """
        Get the API key.
        """
        try:
            return ConfigManager().get_value('api_key', 'key')
        except Exception as e:
            logger.error("Error getting API key"+str(e))
            raise CustomException()

    def delete_key(self):
        """
        Delete the API key.
        """
        try:
            ConfigManager().remove_value("api_key", "key")
        except Exception as e:
            logger.error("Error deleting API key"+str(e))
            raise CustomException()