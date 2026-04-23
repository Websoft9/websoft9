import os
import json
import configparser
from typing import Dict
from src.core.exception import CustomException
from src.core.logger import logger
from src.schemas.appSettings import AppSettings

class SettingsManager:
    """
    Settings Manager

    This class is used to read and write settings from the config file

    Attributes:
        config_file_path (str): The absolute path of the config file
        config (ConfigParser): The config parser object

    Methods:
        read_all: Read all the settings from the config file
        write_all: Write all the settings to the config file
        read_section: Read a section from the config file
        read_key: Read a key from a section in the config file
        write_section: Write a key value pair to a section in the config file
    """
    def __init__(self):
        # Get the absolute path of the current file
        script_dir = os.path.dirname(os.path.realpath(__file__))
        # Get the absolute path of the config directory
        config_dir = os.path.join(script_dir, "../config")

        # Set the absolute path of the config file
        self.config_file_path = os.path.join(config_dir, "config.ini")
        self.config_file_path = os.path.abspath(self.config_file_path)

        self.config = configparser.ConfigParser()

    def read_all(self) -> Dict[str, Dict[str, str]]:
        """
        Read all the settings from the config file
        """
        try:
            # Read the config file
            self.config.read(self.config_file_path)
            data = {s:dict(self.config.items(s)) for s in self.config.sections()}
            return AppSettings(**data)
        except Exception as e:
            logger.error(e)
            raise CustomException()

    def read_summary(self) -> dict:
        self.config.read(self.config_file_path)
        version_payload = self._read_version_payload()

        return {
            "groups": [
                {
                    "id": "domain",
                    "items": [
                        self._build_item("domain", "wildcard_domain", self._get_value("domain", "wildcard_domain"), editable=True),
                    ],
                },
                {
                    "id": "certificate",
                    "items": [
                        self._build_item("nginx_proxy_manager", "ssl_cert", self._get_value("nginx_proxy_manager", "ssl_cert"), masked=True),
                        self._build_item("nginx_proxy_manager", "ssl_key", self._get_value("nginx_proxy_manager", "ssl_key"), sensitive=True, masked=True),
                    ],
                },
                {
                    "id": "mirror",
                    "items": [
                        self._build_item("docker_mirror", "url", self._get_value("docker_mirror", "url"), editable=True),
                    ],
                },
                {
                    "id": "internal_access",
                    "items": [
                        self._build_item("nginx_proxy_manager", "base_url", self._get_value("nginx_proxy_manager", "base_url"), editable=True),
                        self._build_item("portainer", "base_url", self._get_value("portainer", "base_url"), editable=True),
                        self._build_item("gitea", "base_url", self._get_value("gitea", "base_url"), editable=True),
                        self._build_item("cockpit", "port", self._get_value("cockpit", "port"), editable=True),
                        self._build_item("api_key", "key", self._get_value("api_key", "key"), sensitive=True, masked=True),
                    ],
                },
                {
                    "id": "upgrade",
                    "items": [
                        self._build_item("upgrade", "target", "apps"),
                        self._build_item("upgrade", "release_channel", "release"),
                        self._build_item("upgrade", "dev_channel", "dev"),
                    ],
                },
                {
                    "id": "version",
                    "items": [
                        self._build_item("version", "product", str(version_payload.get("version", "-"))),
                        *[
                            self._build_item("version_plugins", key, str(value))
                            for key, value in (version_payload.get("plugins") or {}).items()
                        ],
                    ],
                },
            ],
        }

    def write_all(self, data: AppSettings):
        """
        Write all the settings to the config file

        Args:
            data (AppSettings): The settings to be written to the config file
        """
        # Read the config file
        for section, kv in data.model_dump().items():
            # Add section if not exist
            if section not in self.config.sections():
                self.config.add_section(section)
            # Update the key value pair
            for key, value in kv.items():
                self.config.set(section, key, value)
        # Write the config file
        with open(self.filename, 'w') as configfile:
            self.config.write(configfile)

    def read_section(self, section: str) -> Dict[str, str]:
        """
        Read a section from the config file

        Args:
            section (str): The section to be read from the config file

        Returns:
            Dict[str, str]: The key value pairs of the section
        """
        try:
            # Read the config file
            self.config.read(self.config_file_path)
            if section not in self.config.sections():
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Section:{section} does not exist"
                )
            return dict(self.config.items(section))
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error("Error in read_section:"+str(e))
            raise CustomException()
        
    def read_key(self, section: str, key:str) -> str:
        """
        Read a key from a section in the config file

        Args:
            section (str): The section to be read from the config file
            key (str): The key to be read from the section in the config file
        
        Returns:
            str: The value of the key
        """
        try:
            # Read the config file
            self.config.read(self.config_file_path)
            # Check if section exists
            if section not in self.config.sections():
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Section:{section} does not exist"
                )
            # Check if key exists
            if key not in self.config[section]:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Key:{key} does not exist"
                )
            return self.config[section][key]
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error("Error in read_key:"+str(e))
            raise CustomException()
        
    def write_section(self, section: str, key:str,value:str):
        """
        Write a key value pair to a section in the config file

        Args:
            section (str): The section to be read from the config file
            key (str): The key to be written to the section in the config file
            value (str): The value to be written to the section in the config file
        """
        try:
            # Read the config file
            self.config.read(self.config_file_path)
            # Check if section exists
            if section not in self.config.sections():
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Section:{section} does not exist"
                )
            # Check if key exists
            if key not in self.config[section]:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Key:{key} does not exist"
                )
            # Update the key value pair
            self.config.set(section, key, value)
            with open(self.config_file_path, 'w') as configfile:
                self.config.write(configfile)
            return self.read_section(section)
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error("Error in write_section:"+str(e))
            raise CustomException()

    def _get_value(self, section: str, key: str) -> str:
        return self.config.get(section, key, fallback="")

    def _build_item(self, section: str, key: str, value: str, *, sensitive: bool = False, masked: bool = False, editable: bool = False) -> dict:
        display_value = value
        if masked:
            display_value = self._mask_value(value)

        return {
            "group": section,
            "key": key,
            "value": display_value,
            "sensitive": sensitive,
            "masked": masked,
            "editable": editable,
        }

    def _mask_value(self, value: str) -> str:
        if not value:
            return "Not configured"
        if len(value) <= 6:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"

    def _read_version_payload(self) -> dict:
        candidate_path = os.path.abspath(os.path.join(os.path.dirname(self.config_file_path), "../../../version.json"))
        if not os.path.exists(candidate_path):
            return {}

        with open(candidate_path, "r", encoding="utf-8") as file:
            return json.load(file)