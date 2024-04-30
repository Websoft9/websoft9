from dotenv import set_key, unset_key, dotenv_values
import os
import re
from src.core.logger import logger
from src.core.exception import CustomException

class EnvHelper:
    def __init__(self, dotenv_path='.env'):
        self.dotenv_path = dotenv_path
        if not os.path.exists(dotenv_path):
            logger.error(f"{dotenv_path} does not exist.")
            raise CustomException()
        
    def get_all_values(self):
        try:
            return dotenv_values(self.dotenv_path)
        except Exception as e:
            logger.error(f"Error getting values from {self.dotenv_path}: {e}")
            raise CustomException()

    def get_value(self, key):
        try:
            # values = dotenv_values(self.dotenv_path)
            # return values.get(key)
            
            values = dotenv_values(self.dotenv_path)

            def resolve_value(value):
                # This pattern matches 'key' that starts with a '$' and is followed by an alphanumeric string or underscore
                pattern = r'\$\{?(\w+)\}?'
                
                # While there are variables to resolve in the value
                while re.search(pattern, value):
                    value = re.sub(pattern, lambda match: resolve_value(values.get(match.group(1), '')), value)
                
                return value
            
            if key not in values:
                return None

            return resolve_value(values.get(key))
        except Exception as e:
            logger.error(f"Error getting {key} from {self.dotenv_path}: {e}")
            raise CustomException()

    def set_value(self, key, value):
        try:
            set_key(self.dotenv_path, key, value)
        except Exception as e:
            logger.error(f"Error setting {key} to {value} in {self.dotenv_path}: {e}")
            raise CustomException()
