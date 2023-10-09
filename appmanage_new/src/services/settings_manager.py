import os
import configparser
from typing import Dict
from src.core.exception import CustomException
from src.core.logger import logger
from src.schemas.appSettings import AppSettings

class SettingsManager:
    def __init__(self):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        config_dir = os.path.join(script_dir, "../config")

        self.config_file_path = os.path.join(config_dir, "config.ini")
        self.config_file_path = os.path.abspath(self.config_file_path)

        self.config = configparser.ConfigParser()

    def read_all(self) -> Dict[str, Dict[str, str]]:
        try:
            self.config.read(self.config_file_path)
            data = {s:dict(self.config.items(s)) for s in self.config.sections()}
            return AppSettings(**data)
        except Exception as e:
            logger.error(e)
            raise CustomException()

    def write_all(self, data: AppSettings):
        for section, kv in data.model_dump().items():
            if section not in self.config.sections():
                self.config.add_section(section)
            for key, value in kv.items():
                self.config.set(section, key, value)
        with open(self.filename, 'w') as configfile:
            self.config.write(configfile)