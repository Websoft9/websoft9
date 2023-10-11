import secrets
import hashlib
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger

class APIKeyManager:
    def generate_key(self):
        try:
            base = secrets.token_urlsafe(32)
            key = hashlib.sha256(base.encode()).hexdigest()
            ConfigManager().set_value('api_key', 'key', key)
            return key
        except Exception as e:
            logger.error("Error generating API key"+str(e))
            raise CustomException()

    def delete_key(self):
        try:
            ConfigManager().remove_value("api_key", "key")
        except Exception as e:
            logger.error("Error deleting API key"+e)
            raise CustomException()