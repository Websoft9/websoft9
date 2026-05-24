import base64
from typing import Any, Dict, List
import json
import os
import shutil
import random
import ipaddress
import re
import tempfile
import urllib.request
from urllib.parse import urlsplit
import yaml
import time
import zipfile
from datetime import datetime, timedelta, timezone
import docker
import requests
import asyncio
import aiodocker
import asyncio
from textwrap import dedent
from typing import Tuple
from datetime import datetime
from pathlib import Path
from src.core.config import ConfigManager
from src.core.envHelper import EnvHelper
from src.core.exception import CustomException
from src.schemas.appInstall import appInstall
from src.schemas.appResponse import AppResponse
from src.services.common_check import check_apps_number, check_endpointId
from src.services.git_manager import GitManager
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.core.logger import logger
from src.services.integration_credentials import IntegrationCredentialProvider
from src.services.proxy_manager import ProxyManager
from src.utils.async_utils import AsyncWrapper
from src.utils.file_manager import FileHelper
from src.utils.password_generator import PasswordGenerator
from tenacity import retry, stop_after_attempt, wait_fixed
from src.utils.async_utils import AsyncWrapper

from src.services.app_status import appInstalling, appInstallingError,start_app_installation,remove_app_installation,modify_app_information,remove_app_from_errors_by_app_id,add_installing_logs,remove_installation_logs


class AppManger:
    # 简单的类级缓存
    _cache = {}
    _cache_timestamps = {}
    _cache_ttl = 300  # 5分钟缓存
    _missing_stack_containers_error = "No containers were created for this stack."
    
    @classmethod
    def clear_cache(cls):
        """清除所有缓存"""
        cls._cache.clear()
        cls._cache_timestamps.clear()
    
    @classmethod 
    def clear_cache_by_pattern(cls, pattern: str):
        """根据模式清除缓存"""
        keys_to_remove = [key for key in cls._cache.keys() if pattern in key]
        for key in keys_to_remove:
            cls._cache.pop(key, None)
            cls._cache_timestamps.pop(key, None)

    def _get_capability_flags(self, app_name: str | None) -> tuple[bool, bool]:
        normalized_name = (app_name or "").strip()
        if not normalized_name:
            return False, False

        system_config = ConfigManager("system.ini")
        php_apps = {
            item.strip()
            for item in (system_config.get_value("php_apps", "keys") or "").split(",")
            if item.strip()
        }
        monitor_apps = {
            item.strip()
            for item in (system_config.get_value("appmonitor", "keys") or "").split(",")
            if item.strip()
        }

        return normalized_name in php_apps, normalized_name in monitor_apps

    def _parse_app_env(self, app_env: list[str] | None) -> tuple[dict[str, str], str | None, str | None, str | None, str | None, str | bool]:
        app_env_format: dict[str, str] = {}
        app_name = None
        app_dist = None
        app_version = None
        w9_url = None
        w9_url_replace: str | bool = False

        for item in app_env or []:
            parts = item.split("=", 1)
            if len(parts) == 2:
                key, value = parts
            else:
                key = parts[0]
                value = ""

            app_env_format[key] = value
            if key == "W9_APP_NAME":
                app_name = value
            elif key == "W9_DIST":
                app_dist = value
            elif key == "W9_VERSION":
                app_version = value
            elif key == "W9_URL_REPLACE":
                w9_url_replace = value
            elif key == "W9_URL":
                w9_url = value

        return app_env_format, app_name, app_dist, app_version, w9_url, w9_url_replace

    def _read_compose_metadata_safe(self, app_id: str) -> dict[str, Any]:
        try:
            from src.services.compose_app_manager import _read_compose_metadata
            return _read_compose_metadata(GiteaManager(), app_id)
        except Exception:
            return {}

    def _enrich_proxy_hosts(self, proxy_hosts: list[dict] | None, w9_url_replace: str | bool = False, w9_url: str | None = None) -> list[dict]:
        enriched_hosts: list[dict] = []
        for proxy_host in proxy_hosts or []:
            host = dict(proxy_host)
            host["w9_url_replace"] = w9_url_replace
            host["w9_url"] = w9_url
            enriched_hosts.append(host)
        return enriched_hosts

    def _group_proxy_hosts_by_app(self, proxy_hosts: list[dict] | None) -> dict[str, list[dict]]:
        proxy_hosts_by_app: dict[str, list[dict]] = {}
        for proxy_host in proxy_hosts or []:
            app_id = proxy_host.get("forward_host")
            if isinstance(app_id, str) and app_id:
                proxy_hosts_by_app.setdefault(app_id, []).append(proxy_host)
        return proxy_hosts_by_app

    def _get_proxy_hosts_safe(self) -> list[dict]:
        try:
            return ProxyManager().get_proxy_hosts()
        except CustomException as exc:
            logger.warning(f"Proxy host listing unavailable during app inventory: {exc.details or exc.message}")
            return []
        except Exception as exc:
            logger.warning(f"Proxy host listing unavailable during app inventory: {exc}")
            return []

    def _get_proxy_host_by_app_safe(self, app_id: str) -> list[dict]:
        try:
            return ProxyManager().get_proxy_host_by_app(app_id)
        except CustomException as exc:
            logger.warning(f"Proxy host lookup unavailable for app {app_id}: {exc.details or exc.message}")
            return []
        except Exception as exc:
            logger.warning(f"Proxy host lookup unavailable for app {app_id}: {exc}")
            return []

    def _group_volumes_by_app(self, volumes: list[dict] | None) -> dict[str, list[dict]]:
        volumes_by_app: dict[str, list[dict]] = {}
        for volume in volumes or []:
            labels = volume.get("Labels") or {}
            app_id = labels.get("com.docker.compose.project")
            if isinstance(app_id, str) and app_id:
                volumes_by_app.setdefault(app_id, []).append(volume)
        return volumes_by_app

    def _normalize_locale(self, locale: str | None) -> str:
        normalized_locale = (locale or "en").strip().lower()
        return "zh" if normalized_locale.startswith("zh") else "en"

    def _get_default_media_path(self, locale: str | None, kind: str) -> str:
        normalized_locale = self._normalize_locale(locale)
        if kind == "screenshot":
            return "/default-screenshot.png" if normalized_locale == "zh" else "/default-screenshot-en.png"
        return "/default.png" if normalized_locale == "zh" else "/default-en.png"

    def _normalize_remote_media_url(self, remote_url: str | None, locale: str | None, kind: str) -> str:
        fallback_path = self._get_default_media_path(locale, kind)
        normalized_url = (remote_url or "").strip()
        if not normalized_url:
            return fallback_path

        if normalized_url.startswith("/"):
            return normalized_url

        parsed = urlsplit(normalized_url)
        if parsed.scheme not in {"http", "https"}:
            return fallback_path
        return normalized_url

    def _normalize_available_app_media(self, item: dict[str, object], locale: str | None) -> dict[str, object]:
        normalized_item = dict(item)

        logo = normalized_item.get("logo")
        normalized_logo = dict(logo) if isinstance(logo, dict) else {}
        normalized_logo["imageurl"] = self._normalize_remote_media_url(normalized_logo.get("imageurl"), locale, "logo")
        normalized_item["logo"] = normalized_logo

        screenshots_value = normalized_item.get("screenshots")
        normalized_screenshots: list[dict[str, object]] = []
        if isinstance(screenshots_value, list):
            for screenshot in screenshots_value:
                if not isinstance(screenshot, dict):
                    continue

                normalized_screenshot = dict(screenshot)
                normalized_screenshot["value"] = self._normalize_remote_media_url(normalized_screenshot.get("value"), locale, "screenshot")
                normalized_screenshots.append(normalized_screenshot)

        if not normalized_screenshots:
            normalized_screenshots.append(
                {
                    "id": f"{normalized_item.get('key', 'app')}-default-screenshot",
                    "key": "default",
                    "value": self._get_default_media_path(locale, "screenshot"),
                }
            )

        normalized_item["screenshots"] = normalized_screenshots
        return normalized_item

    def _is_stale_install_task(self, install_task: dict, now: datetime, timeout_minutes: int = 30) -> bool:
        updated_at = install_task.get("updated_at")
        if not isinstance(updated_at, str) or not updated_at:
            return False

        try:
            updated_at_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return False

        if updated_at_dt.tzinfo is None:
            updated_at_dt = updated_at_dt.replace(tzinfo=timezone.utc)

        return now - updated_at_dt > timedelta(minutes=timeout_minutes)

    def _resolve_stack_runtime_state(self, stack_status: int, stack_containers: list[dict] | None) -> Tuple[int, str | None]:
        if stack_status == 1 and not stack_containers:
            return 4, self._missing_stack_containers_error

        if stack_status == 1 and stack_containers:
            normalized_states = {
                str(container.get("State") or container.get("Status") or "").strip().lower()
                for container in stack_containers
            }
            running_states = {"running", "healthy"}
            if normalized_states and normalized_states.isdisjoint(running_states):
                return 4, "Containers were created for this stack but none of them are running."

        return stack_status, None

    def _ensure_media_asset(self, file_name: str) -> str:
        base_path = ConfigManager("system.ini").get_value("app_media", "path")
        asset_path = os.path.join(base_path, file_name)
        if os.path.exists(asset_path):
            return asset_path

        try:
            self._sync_media_assets_from_artifact(base_path)
        except Exception as exc:
            logger.error(f"Runtime media asset sync failed while restoring {file_name}: {exc}")

        if not os.path.exists(asset_path):
            logger.error(f"App media asset missing after sync attempt: {asset_path}")
            raise CustomException(status_code=500, message="Internal Server Error", details=f"Required app media asset is missing: {file_name}")

        return asset_path

    def _sync_media_assets_from_artifact(self, base_path: str) -> None:
        media_json_dir = Path(base_path)
        target_dir = media_json_dir.parent
        marker_path = media_json_dir / "product_en.json"
        if marker_path.exists():
            return

        artifact_base = os.getenv("WEBSOFT9_ARTIFACT_BASE", "https://artifact.websoft9.com").rstrip("/")
        version_file = Path("/websoft9/apphub/src/config/product_metadata.json")
        channel = "release"
        if version_file.exists():
            try:
                version = json.loads(version_file.read_text(encoding="utf-8")).get("version", "")
                if "rc" in version:
                    channel = "dev"
            except Exception:
                channel = "release"

        package_name = os.getenv("WEBSOFT9_MEDIA_PACKAGE", "media-dev.zip" if channel == "dev" else "media-latest.zip")
        package_url = f"{artifact_base}/{channel}/websoft9/plugin/media/{package_name}"

        with tempfile.TemporaryDirectory(prefix="websoft9-media-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            zip_path = temp_dir / package_name
            extract_dir = temp_dir / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            request = urllib.request.Request(
                package_url,
                headers={
                    "User-Agent": "Websoft9-AppHub/1.0",
                    "Accept": "application/zip,application/octet-stream;q=0.9,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(request) as response, zip_path.open("wb") as output:
                shutil.copyfileobj(response, output)

            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_dir)

            source_root = extract_dir / "media"
            if not source_root.exists():
                children = [child for child in extract_dir.iterdir() if child.is_dir()]
                source_root = children[0] if len(children) == 1 else extract_dir

            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_root, target_dir, dirs_exist_ok=True)

        if not marker_path.exists():
            raise RuntimeError(f"Media assets are still missing after artifact sync: {marker_path}")

    def get_php_info(self, app_id: str, endpointId: int = None):
        try:
            portainerManager = PortainerManager()

            if endpointId:
                check_endpointId(endpointId, portainerManager)
            else:
                endpointId = portainerManager.get_local_endpoint_id()

            if not portainerManager.check_stack_exists(app_id, endpointId):
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"{app_id} Not Found"
                )

            app_containers = portainerManager.get_containers_by_stack_name(app_id, endpointId)
            if not app_containers:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details="No containers found for this app"
                )

            docker_client = docker.from_env()
            candidate_containers = sorted(
                app_containers,
                key=lambda container: (
                    0 if container.get("State") == "running" else 1,
                    0 if f"/{app_id}" in container.get("Names", []) else 1,
                ),
            )

            for candidate in candidate_containers:
                candidate_id = candidate.get("Id", "")
                if not candidate_id:
                    continue

                try:
                    container = docker_client.containers.get(candidate_id)
                    php_version_result = container.exec_run("php -v")
                    php_modules_result = container.exec_run("php -m")
                except docker.errors.APIError:
                    continue

                if php_version_result.exit_code != 0 or php_modules_result.exit_code != 0:
                    continue

                php_version_raw = php_version_result.output.decode("utf-8", errors="ignore")
                php_modules_raw = php_modules_result.output.decode("utf-8", errors="ignore")

                version_match = re.search(r"PHP\s+(\d+\.\d+\.\d+)", php_version_raw)
                php_version = f"PHP {version_match.group(1)}" if version_match else php_version_raw.strip()

                categorized_modules = {"PHP Modules": []}
                current_category = "PHP Modules"

                for module in php_modules_raw.strip().splitlines():
                    normalized_module = module.strip()
                    if not normalized_module:
                        continue

                    if normalized_module.startswith("[") and normalized_module.endswith("]"):
                        current_category = normalized_module[1:-1]
                        categorized_modules[current_category] = []
                        continue

                    categorized_modules.setdefault(current_category, []).append(normalized_module)

                return {
                    "version": php_version,
                    "modules": categorized_modules,
                }

            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="PHP runtime is not available for any running container in this app"
            )
        except CustomException as e:
            raise e
        except docker.errors.NotFound:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Main PHP container not found"
            )
        except Exception as e:
            logger.error(f"Get php info by app_id:{app_id} error:{e}")
            raise CustomException()

    def request_php_migration(self, app_id: str, target_version: str, remarks: str, endpointId: int = None):
        try:
            php_info = self.get_php_info(app_id, endpointId)
            app_detail = self.get_app_by_id(app_id, endpointId)
            webhook_url = ConfigManager("system.ini").get_value("webhook", "wechat")

            normalized_target_version = (target_version or "").strip()
            normalized_remarks = (remarks or "").strip()

            if not normalized_target_version:
                raise CustomException(status_code=400, message="Invalid Request", details="Target PHP version is required")
            if not normalized_remarks:
                raise CustomException(status_code=400, message="Invalid Request", details="Migration remarks are required")
            if not webhook_url:
                raise CustomException(status_code=500, message="Invalid Request", details="Webhook URL is not configured")

            app_name = app_detail.get("app_name") or app_detail.get("name") or app_id
            current_version = php_info.get("version") or "Unknown"

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": dedent(
                        f"""
                        <font color="warning">PHP版本迁移申请</font>
                        >应用名称：<font color="comment">{app_name}</font>
                        >应用ID：<font color="comment">{app_id}</font>
                        >当前版本：<font color="comment">{current_version}</font>
                        >目标版本：<font color="comment">PHP {normalized_target_version}</font>
                        >备注信息：<font color="comment">{normalized_remarks}</font>
                        """
                    ).strip(),
                },
            }

            response = requests.post(webhook_url, json=payload, timeout=15)
            response.raise_for_status()

            response_body = response.json() if response.content else {}
            if response_body.get("errcode", 0) != 0:
                raise CustomException(status_code=502, message="Webhook Failed", details=response_body.get("errmsg", "PHP migration request webhook rejected the payload"))

            return {"message": "Success", "details": "PHP migration request submitted successfully"}
        except CustomException as e:
            raise e
        except requests.RequestException as e:
            logger.error(f"Request php migration by app_id:{app_id} error:{e}")
            raise CustomException(status_code=502, message="Webhook Failed", details="Failed to submit the PHP migration request")
        except Exception as e:
            logger.error(f"Request php migration by app_id:{app_id} error:{e}")
            raise CustomException()

    def get_catalog_apps(self,locale:str):
        """
        Get catalog apps

        Args:
            locale (str): The language to get catalog apps from.
        """
        try:
            normalized_locale = self._normalize_locale(locale)
            app_media_path = self._ensure_media_asset(f"catalog_{normalized_locale}.json")
            
            # Get the app catalog list
            with open(app_media_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except (CustomException,Exception) as e:
            logger.error(f"Get app'catalog error:{e}")
            raise CustomException()

    def get_available_apps(self, locale: str):
        """
        Get available apps (Performance Optimized Version)

        Args:
            locale (str): The language to get available apps from.
        """
        # 预先获取初始应用过滤条件，用于缓存key
        normalized_locale = self._normalize_locale(locale)
        initial_apps = ConfigManager("config.ini").get_value("initial_apps", "keys")
        
        # 缓存检查 - 包含配置信息在key中
        cache_key = f"available_apps_{normalized_locale}_{initial_apps or 'all'}"
        current_time = time.time()
        
        # 检查缓存是否存在且未过期
        if (cache_key in self._cache and 
            cache_key in self._cache_timestamps and 
            current_time - self._cache_timestamps[cache_key] < self._cache_ttl):
            return self._cache[cache_key]
        
        try:
            # 预先读取所有配置，避免重复读取
            config_manager = ConfigManager("system.ini")
            app_lib_path = config_manager.get_value("docker_library", "path")
            app_media_path = self._ensure_media_asset(f"product_{normalized_locale}.json")
            
            # Get the app available list
            with open(app_media_path, "r", encoding='utf-8') as f:
                data = json.load(f)
            
            # 使用已获取的配置，避免重复读取
            app_keys_filter = set(initial_apps.split(",")) if initial_apps else None
            
            # 如果有过滤条件，先过滤数据，减少后续处理量
            if app_keys_filter:
                data = [item for item in data if item.get("key") in app_keys_filter]
            
            # 关键优化：批量收集需要处理的环境文件路径
            env_files_to_read = []
            item_key_map = {}  # 建立索引映射
            
            for item in data:
                key = item.get("key")
                if key:
                    env_path = f"{app_lib_path}/{key}/.env"
                    if os.path.exists(env_path):
                        env_files_to_read.append(env_path)
                        item_key_map[env_path] = item
                    else:
                        # 文件不存在时直接设置默认值
                        item["settings"] = {}
                        item["is_web_app"] = False
            
            # 批量解析环境变量内容 - 使用EnvHelper的dotenv_values方法
            for env_path in env_files_to_read:
                item = item_key_map[env_path]
                try:
                    # 使用EnvHelper读取环境变量，自动处理引号等问题
                    env_helper = EnvHelper(env_path)
                    all_values = env_helper.get_all_values()
                    
                    # 检查是否为web应用
                    is_web_app = "W9_URL" in all_values
                    
                    # 只获取以_SET结尾且以W9_开头的变量
                    settings = {key: value for key, value in all_values.items() 
                               if key.endswith("_SET") and key.startswith("W9_")}
                    
                    item["settings"] = settings
                    item["is_web_app"] = is_web_app
                except Exception as e:
                    logger.warning(f"Failed to process env file {env_path}: {e}")
                    item["settings"] = {}
                    item["is_web_app"] = False

            data = [self._normalize_available_app_media(item, normalized_locale) for item in data if isinstance(item, dict)]
            
            # 缓存结果
            self._cache[cache_key] = data
            self._cache_timestamps[cache_key] = current_time
            
            return data
            
        except (CustomException,Exception) as e:
            logger.error(f"Get available apps error:{e}")
            raise CustomException()

    def _get_available_app_logo_map(self, locale: str | None) -> dict[str, str]:
        normalized_locale = self._normalize_locale(locale)
        try:
            available_apps = self.get_available_apps(normalized_locale)
        except Exception as exc:
            logger.warning(f"Failed to resolve available app logos for locale {normalized_locale}: {exc}")
            return {}

        logo_map: dict[str, str] = {}
        for item in available_apps or []:
            if not isinstance(item, dict):
                continue

            key = str(item.get("key") or "").strip().lower()
            logo = item.get("logo")
            image_url = ""
            if isinstance(logo, dict):
                image_url = str(logo.get("imageurl") or "").strip()

            if key and image_url:
                logo_map[key] = image_url

        return logo_map

    def _resolve_available_app_logo_url(self, logo_map: dict[str, str], app_name: str | None, app_id: str | None) -> str | None:
        candidate = (app_name or "").strip().lower()
        if candidate:
            logo_url = logo_map.get(candidate)
            if logo_url:
                return logo_url

        return None

    def create_installation_tracking(self, app_install: appInstall) -> Tuple[str, str]:
        tracked_app_id = app_install.app_id + "_" + PasswordGenerator.generate_random_string(5)

        # Reserve ports now (template defaults + settings overrides) so concurrent
        # install requests see them before Docker containers are actually started.
        reserved_ports: set = set()
        try:
            library_path = ConfigManager("system.ini").get_value("docker_library", "path")
            env_path = os.path.join(library_path, app_install.app_name, ".env")
            if os.path.exists(env_path):
                with open(env_path) as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if not _line or _line.startswith('#') or '=' not in _line:
                            continue
                        _k, _, _v = _line.partition('=')
                        if 'PORT_SET' in _k:
                            try:
                                reserved_ports.add(int(_v.strip()))
                            except ValueError:
                                pass
        except Exception as _e:
            logger.warning(f"Port reservation: could not read template .env: {_e}")
        if app_install.settings:
            for _key, _val in app_install.settings.items():
                if 'PORT_SET' in _key:
                    try:
                        reserved_ports.add(int(_val))
                    except (ValueError, TypeError):
                        pass

        tracking_id = start_app_installation(tracked_app_id, app_install.app_name, reserved_ports=reserved_ports)
        return tracked_app_id, tracking_id

    def get_apps(self,endpointId:int = None, locale: str = "en"):
        """
        Get apps

        Args:
            endpointId (int, optional): The endpoint id. Defaults to None.
            locale (str, optional): Locale used to resolve app media. Defaults to "en".
        """
        # Get the portainer manager
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
            check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        try:
            # Set the apps info for response
            apps_info = []
            logo_map = self._get_available_app_logo_map(locale)
            # Get the stacks by endpointId from portainer
            stacks = portainerManager.get_stacks(endpointId)
            all_containers = portainerManager.get_containers(endpointId)
            proxy_hosts_by_app = self._group_proxy_hosts_by_app(self._get_proxy_hosts_safe())

            stack_names = {
                stack.get("Name")
                for stack in stacks
                if stack.get("Name") is not None
            }

            containers_by_project: dict[str, list[dict]] = {}
            for container in all_containers:
                container_labels = container.get("Labels") or {}
                container_project = container_labels.get("com.docker.compose.project")
                if isinstance(container_project, str) and container_project:
                    containers_by_project.setdefault(container_project, []).append(container)

            for stack in stacks:
                stack_name = stack.get("Name",None)
                if stack_name is not None:
                    stack_status = stack.get("Status", 0)
                    gitConfig = stack.get("GitConfig", {}) or {}
                    creationDate = stack.get("CreationDate", "")
                    domain_names = self._enrich_proxy_hosts(proxy_hosts_by_app.get(stack_name, []))
                    proxy_enabled = len(domain_names) > 0
                    app_name = None
                    app_dist = None
                    app_version = None
                    app_env_format: dict[str, str] = {}
                    stack_containers = containers_by_project.get(stack_name, [])
                    stack_status, stack_error = self._resolve_stack_runtime_state(stack_status, stack_containers)
                    stack_volumes = portainerManager.get_volumes_by_stack_name(stack_name, endpointId, False)

                    if stack_status == 1 and stack_containers:
                        main_container_id = None
                        for container in stack_containers:
                            if f"/{stack_name}" in container.get("Names", []):
                                main_container_id = container.get("Id", "")
                                break

                        if main_container_id:
                            main_container_info = portainerManager.get_container_by_id(endpointId, main_container_id)
                            app_env = main_container_info.get("Config", {}).get("Env", [])
                            app_env_format, app_name, app_dist, app_version, w9_url, w9_url_replace = self._parse_app_env(app_env)
                            domain_names = self._enrich_proxy_hosts(domain_names, w9_url_replace, w9_url)

                    is_php_app, is_monitor_app = self._get_capability_flags(app_name)

                    app_info = AppResponse(
                        app_id=stack_name,
                        endpointId=endpointId,
                        app_name=app_name,
                        logo_url=self._resolve_available_app_logo_url(logo_map, app_name, stack_name),
                        app_dist=app_dist,
                        app_version=app_version,
                        app_official=True,
                        is_php_app=is_php_app,
                        is_monitor_app=is_monitor_app,
                        proxy_enabled=proxy_enabled,
                        domain_names=domain_names,
                        status=stack_status,
                        creationDate=creationDate,
                        gitConfig=gitConfig,
                        containers=stack_containers,
                        volumes=stack_volumes,
                        env=app_env_format,
                        error=stack_error,
                    )
                    apps_info.append(app_info)

            now = datetime.now(timezone.utc)

            # Get the installing apps. Auto-clean stale tasks that no longer have
            # a Portainer stack or a Gitea repo, otherwise they remain stuck in
            # "Installing" forever after aborted manual/debug runs.
            for app_uuid,app in appInstalling.items(): 
                install_app_id = app.get("app_id", None)
                stack_exists = bool(install_app_id) and install_app_id in stack_names
                repo_exists = False
                if install_app_id:
                    try:
                        repo_exists = GiteaManager().check_repo_exists(install_app_id)
                    except Exception:
                        repo_exists = False

                if self._is_stale_install_task(app, now) and not stack_exists and not repo_exists:
                    remove_app_installation(app_uuid)
                    continue

                app_response = AppResponse(
                        app_id = install_app_id,
                        tracking_id = app.get("tracking_id", app_uuid),
                        status = app.get("status", None),
                        app_name = app.get("app_name", None),
                        logo_url = self._resolve_available_app_logo_url(logo_map, app.get("app_name"), install_app_id),
                        app_official = app.get("app_official", None),
                        error = app.get("error", None),
                        logs = app.get("logs", None)
                    )
                if any(app_info.app_id == app_response.app_id for app_info in apps_info):
                    #从apps_info中删除app_id对应的AppResponse
                    apps_info = [app_info for app_info in apps_info if app_info.app_id != app_response.app_id]
                apps_info.append(app_response)

            # Get the installing error apps.
            # Auto-clean stale errors: if the app already appears in apps_info (recovered in Portainer
            # or still being installed), the previous error entry is no longer relevant and can be
            # discarded. This prevents a deleted-from-Portainer app from showing up as Error.
            existing_app_ids = {info.app_id for info in apps_info}
            for app_uuid, app in list(appInstallingError.items()):
                err_app_id = app.get("app_id")
                if err_app_id in existing_app_ids:
                    # App recovered or re-deployed — remove the stale error entry
                    appInstallingError.pop(app_uuid)
                    continue
                app_response = AppResponse(
                    app_id=err_app_id,
                    tracking_id=app.get("tracking_id", app_uuid),
                    status=app.get("status", None),
                    app_name=app.get("app_name", None),
                    logo_url=self._resolve_available_app_logo_url(logo_map, app.get("app_name"), err_app_id),
                    app_official=app.get("app_official", None),
                    error=app.get("error", None),
                    logs=app.get("logs", None),
                )
                apps_info.append(app_response)

            return apps_info
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Get apps error:{e}")
            raise CustomException()

    def get_app_by_id(self,app_id:str,endpointId:int = None, locale: str = "en"):
        """
        Get app by app_id

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        try:
            portainerManager = PortainerManager()
            logo_map = self._get_available_app_logo_map(locale)
            
            # Check the endpointId is exists.
            if endpointId:
                check_endpointId(endpointId, portainerManager)
            else:
                endpointId = portainerManager.get_local_endpoint_id()
            
            # Get stack_info by app_id from portainer
            stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
            if stack_info is None:
                fallback_app = next((app for app in self.get_apps(endpointId, locale) if app.app_id == app_id), None)
                if fallback_app is not None:
                    return fallback_app
                domain_names = self._get_proxy_host_by_app_safe(app_id)
                proxy_enabled = len(domain_names) > 0
                app_name = None
                is_php_app, is_monitor_app = self._get_capability_flags(app_name)
                return AppResponse(
                    app_id=app_id,
                    endpointId=endpointId,
                    app_name=app_name,
                    logo_url=self._resolve_available_app_logo_url(logo_map, app_name, app_id),
                    app_dist=None,
                    app_version=None,
                    app_official=False,
                    is_php_app=is_php_app,
                    is_monitor_app=is_monitor_app,
                    proxy_enabled=proxy_enabled,
                    domain_names=self._enrich_proxy_hosts(domain_names),
                    status=2,
                    creationDate=None,
                    gitConfig={},
                    containers=[],
                    volumes=[],
                    env={},
                )
            # Get the stack_id
            stack_id = stack_info.get("Id",None)
            # Check the stack_id is exists
            if stack_id is None:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"{app_id} Not Found"
                )
            # Get the stack_status
            stack_status = stack_info.get("Status",0)
            # Get the gitConfig
            gitConfig = stack_info.get("GitConfig",{}) or {}
            # Get the creationDate
            creationDate = stack_info.get("CreationDate","")
            # Get the domain_names by app_id from nginx proxy manager
            domain_names = self._get_proxy_host_by_app_safe(app_id)
            # Set the proxy_enabled
            if not domain_names:
                proxy_enabled = False
            else :
                proxy_enabled = True
            # Get the volumes by app_id from portainer
            app_volumes = portainerManager.get_volumes_by_stack_name(app_id,endpointId,False)
            app_containers = portainerManager.get_containers_by_stack_name(app_id,endpointId) if stack_status == 1 else []
            stack_status, stack_error = self._resolve_stack_runtime_state(stack_status, app_containers)

            # if stack is empty(status=2-inactive),can not get it
            if stack_status == 1:
                # Get the main container
                main_container_id = None
                app_env = []
                app_env_format = {} # format app_env to dict
                for container in app_containers:
                    if f"/{app_id}" in container.get("Names", []):
                        main_container_id = container.get("Id", "")
                        break
                if main_container_id:
                    # Get the main container info by main_container_id from portainer
                    main_container_info =  portainerManager.get_container_by_id(endpointId, main_container_id)
                    # Get the env from main_container_info
                    app_env = main_container_info.get("Config", {}).get("Env", [])

                app_env_format, app_name, app_dist, app_version, w9_url, w9_url_replace = self._parse_app_env(app_env)
                domain_names = self._enrich_proxy_hosts(domain_names, w9_url_replace, w9_url)

                compose_metadata = self._read_compose_metadata_safe(app_id)
                if not app_dist:
                    metadata_dist = compose_metadata.get("dist")
                    if isinstance(metadata_dist, str) and metadata_dist.strip():
                        app_dist = metadata_dist.strip()
                if not app_name:
                    metadata_name = compose_metadata.get("app_name")
                    if isinstance(metadata_name, str) and metadata_name.strip():
                        app_name = metadata_name.strip()
                if not app_version:
                    metadata_version = compose_metadata.get("version")
                    if isinstance(metadata_version, str) and metadata_version.strip():
                        app_version = metadata_version.strip()

                is_php_app, is_monitor_app = self._get_capability_flags(app_name)

                # Set the appResponse
                appResponse = AppResponse(
                    app_id = app_id,
                    endpointId = endpointId,
                    app_name = app_name,
                    logo_url = self._resolve_available_app_logo_url(logo_map, app_name, app_id),
                    app_dist = app_dist,
                    app_version = app_version,
                    app_official = True,
                    is_php_app = is_php_app,
                    is_monitor_app = is_monitor_app,
                    proxy_enabled = proxy_enabled,
                    domain_names = domain_names,
                    status = stack_status,
                    creationDate = creationDate,
                    gitConfig = gitConfig,
                    containers = app_containers,
                    volumes = app_volumes,
                    env = app_env_format,
                    error = stack_error,
                )
                return appResponse
            else:
                app_name = None
                compose_metadata = self._read_compose_metadata_safe(app_id)
                inactive_app_dist = str(compose_metadata.get("dist") or "").strip()
                metadata_name = compose_metadata.get("app_name")
                if isinstance(metadata_name, str) and metadata_name.strip():
                    app_name = metadata_name.strip()
                metadata_version = compose_metadata.get("version")
                inactive_app_version = str(metadata_version or "").strip()
                is_php_app, is_monitor_app = self._get_capability_flags(app_name)
                appResponse = AppResponse(
                    app_id = app_id,
                    endpointId = endpointId,
                    app_name = app_name,
                    logo_url = self._resolve_available_app_logo_url(logo_map, app_name, app_id),
                    app_dist = inactive_app_dist,
                    app_version = inactive_app_version,
                    app_official = True,
                    is_php_app = is_php_app,
                    is_monitor_app = is_monitor_app,
                    proxy_enabled = proxy_enabled,
                    domain_names = domain_names,
                    status = stack_status,
                    creationDate = creationDate,
                    gitConfig = gitConfig,
                    containers = app_containers,
                    volumes = app_volumes,
                    env = {},
                    error = stack_error,
                )
                return appResponse
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Get app by app_id:{app_id} error:{e}")
            raise CustomException()
    
    def install_app(self,appInstall: appInstall, endpointId: int = None, tracked_app_id: str = None, tracking_id: str = None):
        """
        Install app

        Args:
            appInstall (appInstall): The app install info.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        # Get the portainer and gitea manager
        portainerManager = PortainerManager()
        giteaManager = GiteaManager()

        # Get the info from appInstall
        app_name = appInstall.app_name
        app_version = appInstall.edition.version
        app_id = tracked_app_id or appInstall.app_id
        proxy_enabled = appInstall.proxy_enabled
        domain_names = appInstall.domain_names
        settings = appInstall.settings

        # Check the endpointId is exists.
        if endpointId is None:
            # Get the local endpointId
            endpointId = portainerManager.get_local_endpoint_id()

        # add app to appInstalling when the request did not pre-register tracking
        app_uuid = tracking_id or start_app_installation(app_id, app_name)
        add_installing_logs(app_uuid, "Initializing installation","")

        # Install app - Step 1 : create repo in gitea
        try:
            repo_url =  giteaManager.create_repo(app_id)
        except CustomException as e:
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # modify app status: error
            modify_app_information(app_uuid,"Create repo error")
            remove_installation_logs(app_uuid)
            logger.error(f"Create repo error:{e}")
            raise CustomException()

        # Install app - Step 2 : initialize local git repo and push to gitea
        try:
            # The source directory.
            library_path = ConfigManager("system.ini").get_value("docker_library", "path")
            local_path = f"{library_path}/{app_name}"

            # Create a temporary directory.
            app_tmp_dir = "/tmp"
            # Get system time
            now = datetime.now()
            # Convert the time to a string
            timestamp_str = now.strftime("%Y%m%d%H%M%S%f")
            # Generate a random number
            rand_num = random.randint(1000, 9999)

            # The temporary directory path.
            app_tmp_dir_path = f"{app_tmp_dir}/{app_name}_{timestamp_str}_{rand_num}"

            # If the temporary directory does not exist, create it.
            if not os.path.exists(app_tmp_dir):
                os.makedirs(app_tmp_dir)

            # If the specific target folder already exists, remove it before copying.
            if os.path.exists(app_tmp_dir_path):
                shutil.rmtree(app_tmp_dir_path)

            # Copy the entire directory.
            shutil.copytree(local_path, app_tmp_dir_path)

            # Modify the env file
            env_file_path = f"{app_tmp_dir_path}/.env"
            envHelper = EnvHelper(env_file_path)

            # Set the install info to env file
            envHelper.set_value("W9_ID", app_id)
            envHelper.set_value("W9_APP_NAME", app_name)
            envHelper.set_value("W9_DIST", "community")
            envHelper.set_value("W9_VERSION", app_version)

            # Verify if a rcode needs to be set
            is_set_rcode = envHelper.get_value("W9_RCODE")
            if is_set_rcode is not None:
                # Set the rcode to env file
                envHelper.set_value("W9_RCODE", PasswordGenerator.generate_random_string_with_rules(12))
            
            # Verify if a password needs to be set
            is_set_password = envHelper.get_value("W9_POWER_PASSWORD")
            if is_set_password is not None:
                # Set the password to env file
                envHelper.set_value("W9_POWER_PASSWORD", PasswordGenerator.generate_strong_password())

            # Set the settings to env file
            if settings:
                for key, value in settings.items():
                    envHelper.set_value(key, value)

            # Verify the app is web app
            is_web_app = envHelper.get_value("W9_URL")
            # url_with_port = envHelper.get_value("W9_URL_WITH_PORT")
            w9_url_with_replace = envHelper.get_value("W9_URL_REPLACE")

            if is_web_app is not None:
                if w9_url_with_replace is None:
                    envHelper.set_value("W9_URL", domain_names[0])
                else:
                    try:
                        ipaddress.ip_address(domain_names[0])
                        #envHelper.set_value("W9_URL", domain_names[0] + ":" + envHelper.get_value("W9_HTTP_PORT_SET"))
                        envHelper.set_value("W9_URL", domain_names[0] + ":" + (envHelper.get_value("W9_HTTP_PORT_SET") or envHelper.get_value("W9_HTTPS_PORT_SET")))
                    except ValueError:
                        envHelper.set_value("W9_URL", domain_names[0])

            # if is_web_app is not None and url_with_port is not None:
            #     try:
            #         ipaddress.ip_address(domain_names[0])
            #         envHelper.set_value("W9_URL", domain_names[0] + ":" + envHelper.get_value("W9_HTTP_PORT_SET"))
            #     except ValueError:
            #         envHelper.set_value("W9_URL", domain_names[0])
                    
            # Commit and push to remote repo
            self._init_local_repo_and_push_to_remote(app_tmp_dir_path,repo_url)
        except CustomException as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid,"Initialize repo error")
            remove_installation_logs(app_uuid)
            logger.error(f"Initialize repo error:{e}")
            raise CustomException()

        # Install app - Step 3 : pull docker image
        try:
            add_installing_logs(app_uuid,"Pulling docker image","")
            self.pull_images_from_yml(app_tmp_dir_path,app_uuid)
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # modify app status: error
            modify_app_information(app_uuid, "Pull docker image error")
            remove_installation_logs(app_uuid)
            logger.error(f"Pull docker image error: {e}")
            raise CustomException()

        stack_id = None

        # Install app - Step 4 : create stack in portainer
        try:
            add_installing_logs(app_uuid,"Starting the services","")
            # Get gitea user_name and user_pwd
            credentials = IntegrationCredentialProvider().get_gitea_credentials()
            user_name = credentials.username
            user_pwd = credentials.password

            # Create stack in portainer
            stack_info = portainerManager.create_stack_from_repository(app_id,endpointId,repo_url,user_name,user_pwd)

            # Get the stack_id
            stack_id = stack_info.get("Id")
            stack_containers = portainerManager.wait_for_stack_containers(app_id, endpointId)
            if not stack_containers:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=self._missing_stack_containers_error,
                )
        except CustomException as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Remove stack and volumes when a stack record was already created.
            if stack_id is not None:
                try:
                    portainerManager.remove_stack_and_volumes(stack_id,endpointId)
                except Exception:
                    portainerManager.remove_vloumes(app_id,endpointId)
            else:
                portainerManager.remove_vloumes(app_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # Rollback: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Remove stack and volumes when a stack record was already created.
            if stack_id is not None:
                try:
                    portainerManager.remove_stack_and_volumes(stack_id,endpointId)
                except Exception:
                    portainerManager.remove_vloumes(app_id,endpointId)
            else:
                portainerManager.remove_vloumes(app_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,"Create stack error")
            remove_installation_logs(app_uuid)
            logger.error(f"Create stack error:{e}")
            raise CustomException()
            
        # Install app - Step 5 : create proxy in nginx proxy manager
        try:
            add_installing_logs(app_uuid,"Configuring the domain","")
            # check the app is web app
            if is_web_app is not None :
                if proxy_enabled and domain_names:
                    # Get the forward port form env file
                    http_port = EnvHelper(env_file_path).get_value("W9_HTTP_PORT")
                    https_port = EnvHelper(env_file_path).get_value("W9_HTTPS_PORT")

                    if http_port:
                        forward_scheme = "http"
                        forward_port = http_port
                    elif https_port:
                        forward_scheme = "https"
                        forward_port = https_port
                    
                    # Get the nginx proxy config path
                    nginx_proxy_path = f"{app_tmp_dir_path}/src/nginx-proxy.conf"
                    if os.path.exists(nginx_proxy_path):
                        # Get the advanced config
                        advanced_config = FileHelper.read_file(nginx_proxy_path)
                        # Create proxy in nginx proxy manager
                        ProxyManager().create_proxy_by_app(domain_names,app_id,forward_port,advanced_config,forward_scheme)
                    else:
                        # Create proxy in nginx proxy manager
                        ProxyManager().create_proxy_by_app(domain_names,app_id,forward_port,forward_scheme=forward_scheme)
        except CustomException as e:
            # Rollback-1: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Rollback-2: remove stack in portainer
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,e.details)
            remove_installation_logs(app_uuid)
            raise
        except Exception as e:
            # Rollback-1: remove repo in gitea
            giteaManager.remove_repo(app_id)
            # Rollback-2: remove stack in portainer
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            # modify app status: error
            modify_app_information(app_uuid,"Create proxy error")
            remove_installation_logs(app_uuid)
            logger.error(f"Create proxy error:{e}")
            raise CustomException()

        # remove app from installing
        remove_app_installation(app_uuid)

        # Remove the tmp dir
        shutil.rmtree(app_tmp_dir_path)

        logger.access(f"Installed app: [{app_id}]")
        add_installing_logs(app_uuid,"Installation complete","")
        # 等待1秒
        time.sleep(1)

    async def redeploy_app(self,app_id:str,pull_image:bool,endpointId:int = None,queue: asyncio.Queue = None):
        """
        Redeploy app

        Args:
            app_id (str): The app id.
            pull_image (bool): Whether to pull the image when redeploying the app.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        async def send_log(message: str):
            if queue:
                await queue.put(message)
                
        await send_log("Initializing Redeployment")
        # Get the appInstallApps
        appInstallApps = AppManger().get_apps(endpointId)

        # Get all apps that are official and active
        app_official = [app for app in appInstallApps if app.app_official == True and app.status == 1 ]

        # if app_id is active,can not check the apps number
        if not any(app.app_id == app_id for app in app_official):
            # Chenck the apps number
            check_apps_number(endpointId)

        #fix bug(上面排除了状态为Inactive的，导致状态为Inactive的不能重建，这里重新加入)
        app_official = [app for app in appInstallApps if app.app_official == True and (app.status == 1 or app.status == 2)]

        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
            check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()

        # validate the app_id is exists in portainer
        await send_log("Verify Application Status")
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_id
        stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
       
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        else:
            credentials = IntegrationCredentialProvider().get_gitea_credentials()
            user_name = credentials.username
            user_pwd = credentials.password

            app_tmp_dir = f"/tmp/{app_id}"
            # if the app_tmp_dir exists, remove it
            if os.path.exists(app_tmp_dir):
                shutil.rmtree(app_tmp_dir)

            # instantiate a GitManager object
            gitManager =GitManager(app_tmp_dir) 

            # 从app中获取 gitConfig属性的URL属性值
            remote_url = [app.gitConfig.get("URL") for app in app_official if app.app_id == app_id][0]

            # Initialize a local git repository from a directory
            gitManager.clone_remote_repo_to_local(remote_url,user_name,user_pwd)
            
            env_file_path = os.path.join(app_tmp_dir, '.env')
            env_helper = EnvHelper(env_file_path)
            #yml_files = [os.path.join(app_tmp_dir, f) for f in os.listdir(app_tmp_dir) if f.endswith('.yml')]
            yml_files = [os.path.join(app_tmp_dir, f) for f in os.listdir(app_tmp_dir) if f == 'docker-compose.yml']

            if not yml_files:
                raise CustomException("No yml files found in the directory")

            # Initialize Docker client with host's Docker socket
            docker_client = aiodocker.Docker()

            async def docker_pull_image(image):
                success = False  # 标志位，跟踪是否成功拉取镜像
                if ":" not in image:  # 若镜像名不包含标签
                    image = f"{image}:latest"  # 自动追加最新标签
                try:
                    # Try pulling the image directly first

                    await send_log(f"Pulling image: {image}")
                    pull_result = docker_client.images.pull(image, stream=True)
                    async for line in pull_result:
                        await send_log(line)
                    success = True  # 成功拉取镜像
                    return
                # except docker.errors.APIError as e:
                #     pass
                except Exception as e:
                    await send_log(f"Failed to pull image: {image}")
                    pass

                 # Get image accelerators
                image_accelerators = self.download_image_accelerators()

                # If direct pull fails, try using accelerators
                for accelerator in image_accelerators:
                    try:
                        # Replace the image name with the accelerator URL
                        accelerated_image = f"{accelerator}/{image}"
                        await send_log(f"Pulling image: {accelerated_image}")
                        pull_result = docker_client.images.pull(accelerated_image, stream=True)
                        async for line in pull_result:
                            await send_log(line)
                        
                        # Tag the image back to its original name
                        await docker_client.images.tag(accelerated_image, image)
                        # Remove the accelerated image tag
                        await docker_client.images.delete(accelerated_image)
                        success = True  # 成功拉取镜像
                        break
                    except docker.errors.APIError as e:
                        logger.error(f"Failed to pull image from {accelerator}: {e}")
                
                # If all attempts fail, raise an exception
                if not success:
                    raise CustomException(f"Failed to pull image: {image}")

            tasks = []
            for yml_file in yml_files:
                with open(yml_file, 'r') as file:
                    compose_content = yaml.safe_load(file)
                    services = compose_content.get('services', {})
                    # for service in services.values():
                    for service_name, service in services.items():
                        if 'build' in service:
                            logger.access(f"Service '{service_name}' has build configuration, skipping image pull.")
                            continue
                        image = service.get('image')
                        if image:
                            # Replace environment variables in the image string
                            image = self._replace_env_variables(image, env_helper)
                            if pull_image: 
                                tasks.append(docker_pull_image(image)) #强制拉取镜像
                            try:
                                # Check if the image already exists
                                await docker_client.images.get(image)
                                continue
                            except aiodocker.exceptions.DockerError:
                                tasks.append(docker_pull_image(image))

            await asyncio.gather(*tasks)

            docker_client.close()

            await send_log("Redeploying stack")
            # redeploy stack

            # portainerManager.redeploy_stack(stack_id,endpointId,pull_image,user_name,user_pwd)
            try:
                await AsyncWrapper.run_sync(
                    portainerManager.redeploy_stack,
                    stack_id,
                    endpointId,
                    False,      #强制设置不拉取镜像，而是通过Websoft9的逻辑来拉取镜像
                    user_name,
                    user_pwd,
                    timeout=300  # 给Portainer重建更宽的完成窗口，避免较慢环境下误判超时
                )
            except CustomException as e:
                await send_log(f"Redeploy stack error: {e}")
                raise e
            
            # Remove the tmp dir
            shutil.rmtree(app_tmp_dir)


            app_info = self.get_app_by_id(app_id,endpointId)
            forward_ports = [domain.get("forward_port") for domain in app_info.domain_names]

            proxy_ids = [domain.get("id") for domain in app_info.domain_names]

            if forward_ports:
                http_port = app_info.env.get("W9_HTTP_PORT")
                https_port = app_info.env.get("W9_HTTPS_PORT")

                forward_port = http_port if http_port else https_port

                forward_ports_str = [str(port) for port in forward_ports]

                if not all(port == forward_port for port in forward_ports_str):
                    for proxy_id in proxy_ids:
                        ProxyManager().update_proxy_port_by_app(proxy_id, forward_port)
                        logger.access(f"Updated proxy port: {forward_port} for app: {app_id}")
            
            await send_log("Redeployment complete")
            # 等待1秒
            time.sleep(5)
            #await send_log(None)
            logger.access(f"Redeployed app: [{app_id}]")
            

    def uninstall_app(self,app_id:str,purge_data:bool,endpointId:int = None):
        """
        Uninstall app

        Args:
            app_id (str): The app id.
            purge_data (bool): Whether to purge data when uninstalling the app.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_id
        stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        
        # get stack status,if stack is empty(status=2-inactive),can not uninstall it
        stack_status = portainerManager.get_stack_by_name(app_id,endpointId).get("Status")
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not uninstall it,you can remove it"
            )
        
        if purge_data:
            # Uninstall app - Step 1 : remove proxy in nginx proxy manager
            # Check the proxy is exists
            proxyManager = ProxyManager()
            # Check the proxy is exists
            proxys_host = proxyManager.get_proxy_host_by_app(app_id)
            # If the proxy is exists, remove it
            if proxys_host:
                # Remove proxy
                proxyManager.remove_proxy_host_by_app(app_id)

            # Uninstall app - Step 2 : remove repo in gitea
            # Check the repo is exists
            giteaManager = GiteaManager()
            is_repo_exists = giteaManager.check_repo_exists(app_id)
            if is_repo_exists:
                # Remove repo
                giteaManager.remove_repo(app_id)
            
            # Uninstall app - Step 3 : remove stack in portainer
            # Get stack_id by app_id from portainer
            stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
            if stack_id is None:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"{app_id} Not Found"
                )
            # remove stack and volumes
            portainerManager.remove_stack_and_volumes(stack_id,endpointId)
            logger.access(f"Uninstalled app: [{app_id}] and removed all data")
        else:
            # down stack
            portainerManager.down_stack(stack_id,endpointId)
            logger.access(f"Uninstalled app: [{app_id}] and keep data")

    def remove_app(self,app_id:str,endpointId:int = None):
        """
        Remove app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_id
        stack_id = portainerManager.get_stack_by_name(app_id,endpointId).get("Id",None)
        if stack_id is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        stack_status = stack_info.get("Status")
        stack_containers = portainerManager.get_containers_by_stack_name(app_id, endpointId) if stack_info else []
        resolved_status, _ = self._resolve_stack_runtime_state(stack_status, stack_containers)
        if resolved_status == 1:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is not inactive, please uninstall it first"
            )
        # Check the proxy is exists
        proxyManager = ProxyManager()
        proxys_host = proxyManager.get_proxy_host_by_app(app_id)
        # If the proxy is exists, remove it
        if proxys_host:
            proxyManager.remove_proxy_host_by_app(app_id)

        # Check the repo is exists
        giteaManager = GiteaManager()
        is_repo_exists = giteaManager.check_repo_exists(app_id)
        if is_repo_exists:
            giteaManager.remove_repo(app_id)
        # remove stack and volumes
        portainerManager.remove_stack_and_volumes(stack_id,endpointId)

        logger.access(f"Removed app: [{app_id}]")

    def remove_error_app(self,app_id:str):
        """
        Remove error app

        Args:
            app_id (str): The error app id.
        """
        # validate the app_id is exists in appInstallingError
        try:
            is_app_in_appInstallingError = any(item['app_id'] == app_id for item in appInstallingError.values())
            if not is_app_in_appInstallingError:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Error App:{app_id}  Not Found"
                )
            # remove app from appInstallingError
            remove_app_from_errors_by_app_id(app_id)
        except CustomException as e:
            raise
        except Exception as e:
            logger.error(f"Remove error app error:{e}")
            raise CustomException()    

        logger.access(f"Removed error app: [{app_id}]")

    def start_app(self,app_id:str,endpointId:int = None):
        """
        Start app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_info by app_id from portainer
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # validate the stack is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not start it,you can redeploy it"
            )
        # start stack
        portainerManager.start_stack(app_id,endpointId)
        logger.access(f"Started app: [{app_id}]")

    def stop_app(self,app_id:str,endpointId:int = None):
        """
        Stop app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.  
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_info by app_id from portainer
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # validate the stack is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not stop it,you can redeploy it"
            )
        # stop stack
        portainerManager.stop_stack(app_id,endpointId)
        logger.access(f"Stopped app: [{app_id}]")

    def restart_app(self,app_id:str,endpointId:int = None):
        """
        Restart app

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # validate the app_id is exists in portainer
        is_stack_exists =  portainerManager.check_stack_exists(app_id,endpointId)
        if not is_stack_exists:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Get stack_info by app_id from portainer
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # validate the stack is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not restart it,you can redeploy it"
            )
        # restart stack
        portainerManager.restart_stack(app_id,endpointId)
        logger.access(f"Restarted app: [{app_id}]")
        
    def get_proxys_by_app(self,app_id:str,endpointId:int = None):
        """
        Get proxys by app_id

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        portainerManager = PortainerManager()
        proxyManager = ProxyManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()

        # Reading proxy access configuration should remain tolerant even when
        # Portainer can no longer resolve the stack by name. The My Apps shell
        # may still surface historical app records or existing proxy bindings.
        # Get the proxys
        return proxyManager.get_proxy_host_by_app(app_id)

    def create_proxy_by_app(self,app_id:str,domain_names:list[str],endpointId:int = None,certificate_id:int | None = None, ssl_forced: bool = False):
        """
        Create proxy by app_id

        Args:
            app_id (str): The app id.
            domain_names (list[str]): The domain names.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # Check the app_id is exists
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        # Check the app is active
        stack_status = stack_info.get("Status",None)
        if stack_status == 2:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is inactive, can not create proxy,you can redeploy it"
            )
        
        # Check the domain_names is exists
        # check_domain_names(domain_names)

        # Get the forward port
        stack_env = self.get_app_by_id(app_id,endpointId).env
        if stack_env:
            # Get the forward_port
            http_port = stack_env.get("W9_HTTP_PORT",None)
            https_port = stack_env.get("W9_HTTPS_PORT",None)
            if http_port:
                forward_scheme = "http"
                forward_port = http_port
            elif https_port:
                forward_scheme = "https"
                forward_port = https_port
            # Create proxy
            if forward_port:
                w9_url = stack_env.get("W9_URL",None)
                w9_url_replace = stack_env.get("W9_URL_REPLACE",None)

                if w9_url and w9_url_replace:
                    # Get the all proxys by app_id
                    all_domain_names = proxyManager.get_proxy_host_by_app(app_id)
                    # if all_domain_names is empty,create proxy
                    if not all_domain_names:
                        # update the env file
                            self._update_gitea_env_file(app_id,w9_url,domain_names[0])           
                            # redeploy app
                            #self.redeploy_app(app_id,False)
                            asyncio.run(self.redeploy_app(app_id, False))
                    else:
                        combined_domain_names = []
                        for item in all_domain_names:
                            combined_domain_names.extend(item['domain_names'])
                        combined_domain_names.extend(domain_names)

                        if w9_url not in combined_domain_names:
                            # update the env file
                            self._update_gitea_env_file(app_id,w9_url,domain_names[0])           
                            # redeploy app
                            #self.redeploy_app(app_id,False)
                            asyncio.run(self.redeploy_app(app_id, False))

                # Get the nginx proxy config
                advanced_config = GiteaManager().get_file_raw_from_repo(app_id, "src/nginx-proxy.conf")
                if advanced_config:
                    proxy_host = proxyManager.create_proxy_by_app(domain_names, app_id, forward_port, advanced_config, forward_scheme=forward_scheme, certificate_id=certificate_id, ssl_forced=ssl_forced)
                else:
                    proxy_host = proxyManager.create_proxy_by_app(domain_names, app_id, forward_port, forward_scheme=forward_scheme, certificate_id=certificate_id, ssl_forced=ssl_forced)

                if proxy_host:
                    logger.access(f"Created domains: {domain_names} for app: [{app_id}]")
                    return proxy_host
                else:
                    logger.error(f"Failed to create proxy host for app: [{app_id}]")
                    raise CustomException()
            else:
                logger.error(f"Get app:{app_id} forward_port error")
                raise CustomException()
        else:
            logger.error(f"Get app:{app_id} env error")
            raise CustomException()

    def remove_proxy_by_app(self,app_id:str,endpointId:int = None):
        """
        Remove proxy by app_id

        Args:
            app_id (str): The app id.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # Check the app_id is exists
        stack_info = portainerManager.get_stack_by_name(app_id,endpointId)
        if stack_info is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} Not Found"
            )
        #  Get the domain_names by app_id from nginx proxy manager
        host = proxyManager.get_proxy_host_by_app(app_id)
        if not host:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"{app_id} is not exists proxy"
            )

        # Remove proxy
        proxyManager.remove_proxy_host_by_app(app_id)
        logger.access(f"Removed all domains for app: [{app_id}]")

    def remove_proxy_by_id(self,proxy_id:int,client_host:str):
        """
        Remove proxy by proxy_id

        Args:
            proxy_id (int): The proxy id.
        """
        # Check the proxy id is exists
        try:
            proxyManager = ProxyManager()
            host = proxyManager.get_proxy_host_by_id(proxy_id)
            if host is None:
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=f"Proxy ID:{proxy_id} Not Found"
                )
            # Get the app_id by proxy_id
            app_id = host.get("forward_host",None)
            if app_id:
                # Get the app_info by app_id 
                app_info = self.get_app_by_id(app_id)
                if app_info:
                    # Get the w9_url and w9_url_replace
                    w9_url_replace = next((element.get("w9_url_replace") for element in app_info.domain_names if element.get("id") == proxy_id), None)
                    w9_url = next((element.get("w9_url") for element in app_info.domain_names if element.get("id") == proxy_id), None)

                    # validate w9_url_replace is true
                    if w9_url_replace:
                        domain_names = host.get("domain_names",None)
                        logger.access(f"domain_names:{domain_names}")
                        if domain_names:
                            # Get the all proxys by app_id
                            app_proxys =  self.get_proxys_by_app(app_id)
                            # if w9_url is in domain_names：
                            if w9_url in domain_names:
                                new_w9_url = None
                                if len(app_proxys) == 1 and app_proxys[0].get("id") == proxy_id:
                                    # 如果w9_url_with_port存在，并且值为: true
                                        new_w9_url = client_host+":"+ (app_info.env.get("W9_HTTP_PORT_SET") or app_info.env.get("W9_HTTPS_PORT_SET"))
                                elif len(app_proxys) > 1:
                                    # Get the first proxy_host
                                    proxy_host = next((proxy for proxy in app_proxys if proxy.get("id") != proxy_id), None)
                                    if proxy_host:
                                        # Get the domain_names
                                        domain_names = proxy_host.get("domain_names",None)
                                        if domain_names:
                                            # Get the first domain_name
                                            new_w9_url = domain_names[0]
                                
                                # update the env file
                                self._update_gitea_env_file(app_id,w9_url,new_w9_url)

                                # redeploy app
                                asyncio.run(self.redeploy_app(app_id,False))
                    # Remove proxy
                    proxyManager.remove_proxy_host_by_id(proxy_id)
                    logger.access(f"Removed domains:{host['domain_names']} for app: [{app_id}]")
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Remove proxy error:{e}")
            raise CustomException()

    def update_proxy_by_app(self,proxy_id:str,domain_names:list[str],endpointId:int = None,certificate_id:int | None = None, ssl_forced: bool | None = None):
        """
        Update proxy by app_id

        Args:
            proxy_id (str): The proxy id.
            domain_names (list[str]): The domain names.
            endpointId (int, optional): The endpoint id. Defaults to None.
        """
        proxyManager = ProxyManager()
        portainerManager = PortainerManager()
        
        # Check the endpointId is exists.
        if endpointId:
              check_endpointId(endpointId, portainerManager)
        else:
            endpointId = portainerManager.get_local_endpoint_id()
        
        # Check the proxy id is exists
        host = proxyManager.get_proxy_host_by_id(proxy_id)
        if host is None:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"Proxy ID:{proxy_id} Not Found"
            )
        
        # Get the app_id by proxy_id
        app_id = host.get("forward_host",None)
        old_domain_names = host.get("domain_names",None)
        logger.access(f"old_domain_names:{old_domain_names}")
        if app_id:
            # Get the app_info by app_id 
            app_info = self.get_app_by_id(app_id)
            if app_info:
                # Get the w9_url and w9_url_replace
                w9_url_replace = next((element.get("w9_url_replace") for element in app_info.domain_names if element.get("id") == proxy_id), None)
                w9_url = next((element.get("w9_url") for element in app_info.domain_names if element.get("id") == proxy_id), None)
                
                # validate w9_url_replace is true
                if w9_url_replace and w9_url:
                    if w9_url in old_domain_names:
                        if w9_url not in domain_names:
                            # update the env file
                            self._update_gitea_env_file(app_id,w9_url,domain_names[0])
                            # redeploy app                            
                            #self.redeploy_app(app_id,False)
                            asyncio.run(self.redeploy_app(app_id,False))

        # Update proxy
        result = proxyManager.update_proxy_by_app(proxy_id,domain_names,certificate_id,ssl_forced)
        logger.access(f"Updated domains:{domain_names} for app: [{host['forward_host']}]")
        return result

    def _init_local_repo_and_push_to_remote(self,local_path:str,repo_url:str):
        """
        Initialize a local git repository from a directory and push to remote repo

        Args:
            local_path (str): The path to the local git repository.
            repo_url (str): The URL of the remote origin.
        """
        try:
            # instantiate a GitManager object
            gitManager =GitManager(local_path) 

            # Initialize a local git repository from a directory
            gitManager.init_local_repo_from_dir()

            credentials = IntegrationCredentialProvider().get_gitea_credentials()
            user_name = credentials.username
            user_pwd = credentials.password

            # Push the local repo to remote repo
            gitManager.push_local_repo_to_remote_repo(repo_url,user_name,user_pwd)
        except (CustomException,Exception) as e:
            logger.error(f"Init local repo and push to remote repo error:{e}")
            raise CustomException()

    def _update_gitea_env_file(self,app_id:str,key:str,value:str):
        """
        Update the env file w9_url

        Args:
            app_id (str): The app id.
            domain_name (str): The domain name.
        """
        try:
            giteaManager = GiteaManager()
            # Get the env file from git repo
            git_env_file = giteaManager.get_file_content_from_repo(app_id,".env")
            # Get the env file sha
            git_env_file_sha = git_env_file.get("sha",None)
            # Get the env file content
            git_env_file_content = git_env_file.get("content",None)
            if git_env_file_sha and git_env_file_content:
                # Get the env file content
                env_file_content = base64.b64decode(git_env_file_content).decode("utf-8")
                # Modify the env file content               
                env_file_content = env_file_content.replace(key,value)
                # base64 encode for env_file_content
                env_file_content = base64.b64encode(env_file_content.encode("utf-8")).decode("utf-8")
                # Update the env file to git repo
                giteaManager.update_file_in_repo(app_id,".env",env_file_content,git_env_file_sha)
                logger.access(f"Update the git repo env file for app: [{app_id}]")
            else:
                logger.error(f"Get the git repo env file error")
                raise CustomException()
        except CustomException as e:
            raise e
        except Exception as e:
            logger.error(f"Update the git repo env file error:{e}")
            raise CustomException()

    def _replace_env_variables(self, text: str, env_helper: EnvHelper) -> str:
        """
        Replace environment variables in the given text using values from env_helper.

        Args:
            text (str): The text containing environment variables.
            env_helper (EnvHelper): The EnvHelper instance to get environment variable values.

        Returns:
            str: The text with environment variables replaced.
        """
        for key, value in env_helper.get_all_values().items():
            text = text.replace(f"${{{key}}}", value)
            text = text.replace(f"${key}", value)
        return text

    @retry(stop=stop_after_attempt(10), wait=wait_fixed(1))
    def download_image_accelerators(self):
        try:
            configured = (ConfigManager("config.ini").get_value("docker_mirror", "url") or "").strip() or "https://artifact.websoft9.com/release/websoft9/mirrors.json"
            if configured.startswith("http://") or configured.startswith("https://"):
                response = requests.get(configured)
                if response.status_code != 200:
                    logger.error(f"Failed to download image accelerators: {response.text}")
                    raise CustomException("Failed to download image accelerators")
                return [self._normalize_image_accelerator(str(item)) for item in response.json().get("mirrors", []) if str(item).strip()]

            return [
                self._normalize_image_accelerator(item)
                for item in configured.replace("\n", ",").split(",")
                if item.strip()
            ]
        except Exception as e:
            logger.error(f"Failed to download image accelerators: {e}")
            return []

    def _normalize_image_accelerator(self, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if normalized.startswith("http://"):
            normalized = normalized[7:]
        elif normalized.startswith("https://"):
            normalized = normalized[8:]
        return normalized

    def pull_images_from_yml(self, app_tmp_dir_path, app_uuid):
        env_file_path = os.path.join(app_tmp_dir_path, '.env')
        env_helper = EnvHelper(env_file_path)
        #yml_files = [os.path.join(app_tmp_dir_path, f) for f in os.listdir(app_tmp_dir_path) if f.endswith('.yml')]
        yml_files = [os.path.join(app_tmp_dir_path, f) for f in os.listdir(app_tmp_dir_path) if f == 'docker-compose.yml']

        if not yml_files:
            raise CustomException("No yml files found in the directory")

        # Get image accelerators
        image_accelerators = self.download_image_accelerators()

        # Initialize Docker client with host's Docker socket
        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')

        def pull_image(image):
            success = False  # 标志位，跟踪是否成功拉取镜像
            try:
                logger.access(f"Pulling image: {image}")
                # Try pulling the image directly first
                for line in docker_client.api.pull(image, stream=True, decode=True):
                    add_installing_logs(app_uuid,"Pulling docker image",line)
                success = True  # 成功拉取镜像
                return
            except Exception as e:
                pass

            # If direct pull fails, try using accelerators
            for accelerator in image_accelerators:
                try:
                    # Replace the image name with the accelerator URL
                    accelerated_image = f"{accelerator}/{image}"
                    logger.access(f"Pulling image from {accelerator}: {accelerated_image}")
                    for line in docker_client.api.pull(accelerated_image, stream=True, decode=True):
                        add_installing_logs(app_uuid,"Pulling docker image",line)
                    
                    # Tag the image back to its original name
                    docker_client.api.tag(accelerated_image, image)
                    # Remove the accelerated image tag
                    docker_client.api.remove_image(accelerated_image)
                    success = True  # 成功拉取镜像
                    return
                except docker.errors.APIError as e:
                    logger.error(f"Failed to pull image from {accelerator}: {e}")
            
            if not success:
                raise CustomException(f"Failed to pull image: {image}")

        for yml_file in yml_files:
            with open(yml_file, 'r') as file:
                compose_content = yaml.safe_load(file)
                services = compose_content.get('services', {})
                # for service in services.values():
                for service_name, service in services.items():
                    if 'build' in service:
                        logger.access(f"Service '{service_name}' has build configuration, skipping image pull.")
                        continue
                    image = service.get('image')
                    if image:
                        # Replace environment variables in the image string
                        image = self._replace_env_variables(image, env_helper)
                        try:
                            # Check if the image already exists
                            logger.access(f"Checking if image exists: {image}")
                            docker_client.images.get(image)
                            continue
                        except docker.errors.ImageNotFound:
                            logger.access(f"Image not found: {image}")
                            pull_image(image)
