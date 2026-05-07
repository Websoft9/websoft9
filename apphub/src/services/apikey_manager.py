import secrets

from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger


class APIKeyManager:
    def generate_key(self):
        try:
            key = secrets.token_hex(32)
            ConfigManager().set_value("api_key", "key", key)
            return key
        except Exception as error:
            logger.error("Error generating API key" + str(error))
            raise CustomException()

    def get_key(self):
        try:
            return ConfigManager().get_value("api_key", "key")
        except Exception as error:
            logger.error("Error getting API key" + str(error))
            raise CustomException()

    def delete_key(self):
        try:
            ConfigManager().remove_value("api_key", "key")
        except Exception as error:
            logger.error("Error deleting API key" + str(error))
            raise CustomException()