import fileinput
from src.core.exception import CustomException
from src.core.logger import logger

class EnvHelper:
    """
    This class is used to modify env file

    Attributes:
        env_file_path (str): Path to env file

    Methods:
        modify_env_values(new_values: dict): Modify env file
    """
    def __init__(self, env_file_path):
        self.env_file_path = env_file_path

    def modify_env_values(self, new_values: dict):
        """
        Modify env file

        Args:
            new_values (dict): New values
            example: {"key1": "value1", "key2": "value2"}
        """
        try:
            with fileinput.FileInput(self.env_file_path, inplace=True) as env_file:
                for line in env_file:
                    for key, new_value in new_values.items():
                        if line.startswith(f"{key}="):
                            print(f"{key}={new_value}")
                            break
                    else:  # Executed when the loop ended normally (no break was encountered).
                        print(line, end='')
                        
        except Exception as e:
            logger.error(f"Modify env file error:{e}")
            raise CustomException()
        
    def get_env_value_by_key(self,key:str):
        """
        Get env value by key

        Args:
            key (str): Key

        Returns:
            str: Value
        """
        try:
            with open(self.env_file_path, "r") as env_file:
                for line in env_file:
                    if line.startswith(f"{key}="):
                        return line.replace(f"{key}=","").strip()
        except Exception as e:
            logger.error(f"Get env value by key error:{e}")
            raise CustomException()