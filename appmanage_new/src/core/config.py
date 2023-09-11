
import configparser


class ConfigManager:
    """
    A class for managing configuration using configparser.

    This class provides methods for reading, modifying, and saving configuration data using the configparser library. 
    It allows getting, setting, and removing values from a configuration file.

    Args:
        config_file_path (str): The path to the configuration file, default is "../config/config.ini".

    Attributes:
        config_file_path (str): The path to the configuration file.
        config (configparser.ConfigParser): The configuration data in memory.
    """

    def __init__(self, config_file_path="../config/config.ini"):
        """
        Initialize a ConfigManager instance.

        Args:
            config_file_path (str): The path to the configuration file.
        """
        self.config_file_path = config_file_path
        self.config = configparser.ConfigParser()
        self.config.read(self.config_file_path)

    def _save_config(self):
        """
        Save the configuration data to the file.

        This method writes the current configuration data to the file specified during initialization.
        """
        with open(self.config_file_path, 'w') as configfile:
            self.config.write(configfile)

    def get_value(self, section, key):
        """
        Get a value from the configuration.

        Args:
            section (str): The section in the configuration.
            key (str): The key to retrieve the value for.

        Returns:
            str: The value associated with the given section and key.
        """
        return self.config.get(section, key)

    def set_value(self, section, key, value):
        """
        Set or update a value in the configuration.

        Args:
            section (str): The section in the configuration.
            key (str): The key to set the value for.
            value (str): The value to set.
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)
        self._save_config()

    def remove_value(self, section, key):
        """
        Remove a value from the configuration.

        Args:
            section (str): The section in the configuration.
            key (str): The key to remove from the configuration.
        """
        if self.config.has_section(section) and self.config.has_option(section, key):
            self.config.remove_option(section, key)
            self._save_config()

    def remove_section(self, section):
        """
        Remove a section from the configuration.
        Remove a section will Remove all configuration items under the section

        Args:
            section (str): The section to remove from the configuration.
        """
        if self.config.has_section(section):
            self.config.remove_section(section)
            self._save_config()