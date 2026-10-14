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
            values = dotenv_values(self.dotenv_path, interpolate=False)
            pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}|\$([A-Za-z_][A-Za-z0-9_]*)'

            def resolve_value(field, visiting):
                if field in visiting:
                    raise CustomException(400, "Invalid environment reference", f"{field}: circular variable reference")
                if field not in values or values[field] is None:
                    raise CustomException(400, "Invalid environment reference", f"{field}: missing variable reference")

                def resolve_reference(match):
                    reference = match.group(1) or match.group(3)
                    default = match.group(2)
                    if reference not in values and default is not None:
                        return os.getenv(reference, default)
                    return resolve_value(reference, visiting | {field})

                return re.sub(pattern, resolve_reference, values[field])

            if key not in values or values[key] is None:
                return None
            return resolve_value(key, set())
        except CustomException:
            raise
        except Exception:
            logger.error(f"Error getting {key} from {self.dotenv_path}")
            raise CustomException() from None

    def set_value(self, key, value):
        try:
            set_key(self.dotenv_path, key, value)
        except Exception:
            logger.error(f"Error setting {key} in {self.dotenv_path}")
            raise CustomException() from None
