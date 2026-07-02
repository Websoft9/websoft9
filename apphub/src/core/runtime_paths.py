import os
from pathlib import Path


_CONFIG_ENV_BY_NAME = {
    "config.ini": "WEBSOFT9_APPHUB_CONFIG_PATH",
    "system.ini": "WEBSOFT9_APPHUB_SYSTEM_CONFIG_PATH",
}


def bundled_apphub_config_path(config_file_name: str = "config.ini") -> str:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    return str((config_dir / config_file_name).resolve())


def resolve_apphub_config_path(config_file_name: str = "config.ini") -> str:
    env_var = _CONFIG_ENV_BY_NAME.get(config_file_name)
    override = (os.getenv(env_var, "") if env_var else "").strip()
    if override:
        return os.path.abspath(override)
    return bundled_apphub_config_path(config_file_name)
