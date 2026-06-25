import os
import shutil
import configparser
import subprocess
import requests
from datetime import datetime
from typing import Dict
from src.core.exception import CustomException
from src.core.logger import logger
from src.schemas.appSettings import AppSettings
from src.services.product_metadata import read_product_edition, read_product_metadata


def _mirror_list_url() -> str:
    """Return the channel-aware URL for the default Docker mirror list."""
    try:
        from src.services.product_runtime_state import read_release_channel
        channel = read_release_channel()
    except Exception:
        channel = "release"
    return f"https://artifact.websoft9.com/websoft9/{channel}/mirrors.json"


DEFAULT_PLATFORM_SELF_SIGNED_CERT_VALIDITY_DAYS = 3650
DEFAULT_PLATFORM_BRAND_TITLE = "Websoft9"
DEFAULT_PLATFORM_BRAND_LOGO_URL = "/websoft9.png"
DEFAULT_PLATFORM_BRAND_BROWSER_TITLE = ""
DEFAULT_PLATFORM_BRAND_FAVICON_URL = "/favicon.ico?v=20260509c"
DEFAULT_PLATFORM_BRAND_APPLE_TOUCH_ICON_URL = "/websoft9.png"

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
        version_payload = read_product_metadata()
        edition = read_product_edition()
        raw_version = str(version_payload.get("version", "")).strip()
        edition_name = str(edition.name or "").strip()
        product_version = f"{edition_name} {raw_version}".strip() or "-"

        return {
            "groups": [
                {
                    "id": "network",
                    "items": [
                        self._build_item("platform_gateway", "bound_domain", self._get_value("platform_gateway", "bound_domain"), editable=True),
                        self._build_item("domain", "wildcard_domain", self._get_value("domain", "wildcard_domain"), editable=True),
                        self._build_item(
                            "platform_gateway",
                            "https_enabled",
                            self._bool_to_string(self._is_platform_https_enabled()),
                            editable=True,
                            metadata={
                                "cert_path": self.config.get("platform_gateway", "ssl_cert", fallback=self._default_ssl_cert_path()),
                                "key_path": self.config.get("platform_gateway", "ssl_key", fallback=self._default_ssl_key_path()),
                                "default_cert_path": self._default_ssl_cert_path(),
                                "default_key_path": self._default_ssl_key_path(),
                                "default_certificate": self._bool_to_string(self._is_default_platform_certificate()),
                                "certificate_validity_days": str(DEFAULT_PLATFORM_SELF_SIGNED_CERT_VALIDITY_DAYS),
                                "cert_expiry": self._read_cert_expiry(),
                            },
                        ),
                        self._build_item(
                            "platform_gateway",
                            "force_https",
                            self._bool_to_string(self._is_force_https_enabled()),
                            editable=True,
                        ),
                    ],
                },
                {
                    "id": "delivery",
                    "items": [
                        self._build_item(
                            "docker_mirror",
                            "url",
                            self._docker_mirror_display_value(),
                            editable=True,
                            metadata={
                                "default_value": "\n".join(self._load_docker_mirror_entries(_mirror_list_url())),
                            },
                        ),
                    ],
                },
                {
                    "id": "version",
                    "items": [
                        self._build_item(
                            "version",
                            "product",
                            product_version,
                            metadata={
                                "version": raw_version,
                                "edition_key": edition.key,
                                "edition_names": edition.names,
                            },
                        ),
                    ],
                },
                {
                    "id": "branding",
                    "items": [
                        self._build_item(
                            "platform_brand",
                            "title",
                            self._get_platform_brand_title(),
                            editable=True,
                        ),
                        self._build_item(
                            "platform_brand",
                            "logo_url",
                            self._get_platform_brand_logo_url(),
                            editable=True,
                            metadata={
                                "default_value": DEFAULT_PLATFORM_BRAND_LOGO_URL,
                            },
                        ),
                        self._build_item(
                            "platform_brand",
                            "favicon_url",
                            self._get_platform_brand_favicon_url(),
                            editable=True,
                            metadata={
                                "default_value": DEFAULT_PLATFORM_BRAND_FAVICON_URL,
                            },
                        ),
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
            if section == "platform_brand":
                return {
                    "title": self._get_platform_brand_title(),
                    "browser_title": self._get_platform_brand_browser_title(),
                    "logo_url": self._get_platform_brand_logo_url(),
                    "favicon_url": self._get_platform_brand_favicon_url(),
                    "apple_touch_icon_url": self._get_platform_brand_apple_touch_icon_url(),
                }
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
            if section == "platform_gateway" and key == "https_enabled":
                return self._write_platform_gateway_boolean_setting("https_enabled", value)
            if section == "platform_gateway" and key == "force_https":
                return self._write_platform_gateway_boolean_setting("force_https", value)
            if section == "platform_gateway" and key == "bound_domain":
                return self._write_platform_gateway_text_setting("bound_domain", value)
            if section == "platform_brand":
                return self._write_platform_brand_setting(key, value)
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

    def _docker_mirror_url(self) -> str:
        configured = self.config.get("docker_mirror", "url", fallback="").strip()
        return configured or _mirror_list_url()

    def _docker_mirror_display_value(self) -> str:
        mirrors = self._load_docker_mirror_entries(self._docker_mirror_url())
        return "\n".join(mirrors)

    def _build_item(self, section: str, key: str, value: str, *, sensitive: bool = False, masked: bool = False, editable: bool = False, metadata: dict | None = None) -> dict:
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
            "metadata": metadata,
        }

    def _mask_value(self, value: str) -> str:
        if not value:
            return "Not configured"
        if len(value) <= 6:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"

    def _is_platform_https_enabled(self) -> bool:
        configured = self.config.get("platform_gateway", "https_enabled", fallback="").strip().lower()
        if configured in {"true", "1", "yes", "on"}:
            return True
        if configured in {"false", "0", "no", "off"}:
            return False

        gateway_default_conf = os.getenv("WEBSOFT9_PLATFORM_GATEWAY_DEFAULT_CONF", "/etc/websoft9/platform-gateway/default.conf")
        if os.path.exists(gateway_default_conf):
            try:
                with open(gateway_default_conf, "r", encoding="utf-8") as file:
                    return "listen 9000 default_server ssl" in file.read()
            except OSError:
                logger.warning("Unable to read platform gateway config when resolving https_enabled")

        return False

    def _is_force_https_enabled(self) -> bool:
        configured = self.config.get("platform_gateway", "force_https", fallback="").strip().lower()
        return configured in {"true", "1", "yes", "on"}

    def _write_platform_gateway_boolean_setting(self, key: str, value: str) -> Dict[str, str]:
        enabled = self._parse_bool(value)

        if not self.config.has_section("platform_gateway"):
            self.config.add_section("platform_gateway")

        if key == "force_https" and enabled and not self._is_platform_https_enabled():
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Platform HTTPS must be enabled before force HTTPS can be enabled",
            )

        self.config.set("platform_gateway", key, self._bool_to_string(enabled))
        if key == "https_enabled" and enabled:
            self.config.set("platform_gateway", "ssl_cert", self._default_ssl_cert_path())
            self.config.set("platform_gateway", "ssl_key", self._default_ssl_key_path())
        if key == "https_enabled" and not enabled:
            self.config.set("platform_gateway", "force_https", "false")

        with open(self.config_file_path, 'w') as configfile:
            self.config.write(configfile)

        self._restart_platform_gateway()
        return self.read_section("platform_gateway")

    def _write_platform_gateway_text_setting(self, key: str, value: str) -> Dict[str, str]:
        if not self.config.has_section("platform_gateway"):
            self.config.add_section("platform_gateway")

        self.config.set("platform_gateway", key, value.strip())
        with open(self.config_file_path, "w") as configfile:
            self.config.write(configfile)

        self._restart_platform_gateway()
        return self.read_section("platform_gateway")

    def write_platform_gateway_settings(
        self,
        *,
        bound_domain: str,
        https_enabled: str,
        force_https: str,
        ssl_cert: str = "",
        ssl_key: str = "",
    ) -> Dict[str, str]:
        self.config.read(self.config_file_path)

        if not self.config.has_section("platform_gateway"):
            self.config.add_section("platform_gateway")

        https_enabled_bool = self._parse_bool(https_enabled)
        force_https_bool = self._parse_bool(force_https)

        if force_https_bool and not https_enabled_bool:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Platform HTTPS must be enabled before force HTTPS can be enabled",
            )

        normalized_cert = (ssl_cert or "").strip()
        normalized_key = (ssl_key or "").strip()

        if https_enabled_bool:
            if bool(normalized_cert) != bool(normalized_key):
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details="Platform certificate and key paths must be provided together",
                )

            if not normalized_cert and not normalized_key:
                current_cert = self.config.get("platform_gateway", "ssl_cert", fallback="").strip()
                current_key = self.config.get("platform_gateway", "ssl_key", fallback="").strip()
                normalized_cert = current_cert or self._default_ssl_cert_path()
                normalized_key = current_key or self._default_ssl_key_path()
        else:
            force_https_bool = False
            normalized_cert = normalized_cert or self.config.get("platform_gateway", "ssl_cert", fallback=self._default_ssl_cert_path()).strip()
            normalized_key = normalized_key or self.config.get("platform_gateway", "ssl_key", fallback=self._default_ssl_key_path()).strip()

        self.config.set("platform_gateway", "bound_domain", (bound_domain or "").strip())
        self.config.set("platform_gateway", "https_enabled", self._bool_to_string(https_enabled_bool))
        self.config.set("platform_gateway", "force_https", self._bool_to_string(force_https_bool))
        self.config.set("platform_gateway", "ssl_cert", normalized_cert)
        self.config.set("platform_gateway", "ssl_key", normalized_key)

        with open(self.config_file_path, "w") as configfile:
            self.config.write(configfile)

        self._restart_platform_gateway()
        return self.read_section("platform_gateway")

    def _is_default_platform_certificate(self) -> bool:
        current_cert = self.config.get("platform_gateway", "ssl_cert", fallback=self._default_ssl_cert_path()).strip()
        current_key = self.config.get("platform_gateway", "ssl_key", fallback=self._default_ssl_key_path()).strip()
        return current_cert == self._default_ssl_cert_path() and current_key == self._default_ssl_key_path()

    def _load_docker_mirror_entries(self, configured_value: str) -> list[str]:
        candidate = (configured_value or "").strip() or _mirror_list_url()
        if candidate.startswith("http://") or candidate.startswith("https://"):
            try:
                response = requests.get(candidate, timeout=10)
                response.raise_for_status()
                payload = response.json()
                mirrors = payload.get("mirrors", []) if isinstance(payload, dict) else []
                normalized = [self._normalize_mirror_entry(str(item)) for item in mirrors if str(item).strip()]
                if normalized:
                    return normalized
            except Exception:
                pass
            # Fetch failed or returned no mirrors — fall through to the
            # built-in default list instead of showing the URL itself.

        if candidate != _mirror_list_url():
            # User-entered value (not the default URL) — treat as
            # comma / newline separated list of mirrors.
            normalized = [
                self._normalize_mirror_entry(item)
                for item in candidate.replace("\n", ",").split(",")
                if item.strip()
            ]
            if normalized:
                return normalized

        # Ultimate fallback: hardcoded built-in mirrors so the UI never
        # shows a raw JSON URL as a mirror entry.
        return [self._normalize_mirror_entry(m) for m in [
            "docker.1ms.run",
            "docker.m.daocloud.io",
            "docker.xuanyuan.me",
            "docker.1panel.live",
        ]]

    def _normalize_mirror_entry(self, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if normalized.startswith("http://"):
            normalized = normalized[7:]
        elif normalized.startswith("https://"):
            normalized = normalized[8:]
        return normalized

    def _restart_platform_gateway(self) -> None:
        try:
            subprocess.Popen(
                [
                    "sh",
                    "-lc",
                    "sleep 0.5 && supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf restart platform-gateway",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            logger.error(f"Failed to schedule platform-gateway restart after HTTPS toggle: {error}")
            raise CustomException(
                status_code=500,
                message="Internal Server Error",
                details="Failed to apply the platform HTTPS change",
            )

    def _parse_bool(self, value: str) -> bool:
        normalized = (value or "").strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise CustomException(
            status_code=400,
            message="Invalid Request",
            details="https_enabled must be a boolean value",
        )

    def _read_cert_expiry(self) -> str:
        """Read certificate expiry date from the current SSL cert file."""
        cert_path = self.config.get("platform_gateway", "ssl_cert", fallback=self._default_ssl_cert_path())
        if not os.path.isfile(cert_path):
            return ""
        try:
            result = subprocess.run(
                ["openssl", "x509", "-enddate", "-noout", "-in", cert_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # Output format: "notAfter=Jun  4 10:00:00 2026 GMT"
                date_str = result.stdout.strip().split("=", 1)[-1]
                dt = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        return ""

    def _bool_to_string(self, value: bool) -> str:
        return "true" if value else "false"

    def _default_ssl_cert_path(self) -> str:
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        return os.getenv("WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH", f"{data_root}/config/platform-gateway/ssl/websoft9-platform-gateway.cert")

    def _default_ssl_key_path(self) -> str:
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        return os.getenv("WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH", f"{data_root}/config/platform-gateway/ssl/websoft9-platform-gateway.key")

    def generate_self_signed_cert(self, domain: str = "", validity_days: int = 3650) -> Dict[str, str]:
        """Generate a self-signed certificate and return the cert/key paths."""
        cert_path = self._default_ssl_cert_path()
        key_path = self._default_ssl_key_path()
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)

        cn = domain.strip() if domain.strip() else "Websoft9"
        subject = f"/CN={cn}"

        result = subprocess.run(
            [
                "openssl", "req", "-x509", "-nodes",
                "-days", str(validity_days),
                "-newkey", "rsa:2048",
                "-keyout", key_path,
                "-out", cert_path,
                "-subj", subject,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise CustomException(
                status_code=500,
                message="Certificate Generation Failed",
                details=result.stderr.strip() or "openssl exited with non-zero status",
            )

        # Also update config
        self.config.read(self.config_file_path)
        if not self.config.has_section("platform_gateway"):
            self.config.add_section("platform_gateway")
        self.config.set("platform_gateway", "ssl_cert", cert_path)
        self.config.set("platform_gateway", "ssl_key", key_path)
        with open(self.config_file_path, "w") as configfile:
            self.config.write(configfile)

        # Restart platform gateway to pick up new cert
        self._restart_platform_gateway()

        return {"ssl_cert": cert_path, "ssl_key": key_path}

    def apply_letsencrypt_cert(self, domain: str, email: str = "") -> Dict[str, str]:
        """Obtain a Let's Encrypt certificate for the given domain via webroot."""
        if not domain.strip():
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Domain is required for Let's Encrypt certificate",
            )
        if not email.strip():
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Contact email is required for Let's Encrypt certificate",
            )

        domain = domain.strip()
        email = email.strip()
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        webroot = os.getenv("WEBSOFT9_NPM_ACME_ROOT", f"{data_root}/letsencrypt-acme-challenge")
        os.makedirs(webroot, exist_ok=True)

        cmd = [
            "certbot", "certonly",
            "--non-interactive", "--agree-tos",
            "--webroot", "-w", webroot,
            "-d", domain,
            "--email", email,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            raise CustomException(
                status_code=500,
                message="Let's Encrypt Certificate Failed",
                details=result.stderr.strip() or result.stdout.strip() or "certbot exited with non-zero status",
            )

        # Certbot writes to /etc/letsencrypt/live/<domain>/
        live_dir = f"/etc/letsencrypt/live/{domain}"
        source_cert = os.path.join(live_dir, "fullchain.pem")
        source_key = os.path.join(live_dir, "privkey.pem")

        if not os.path.isfile(source_cert) or not os.path.isfile(source_key):
            raise CustomException(
                status_code=500,
                message="Let's Encrypt Certificate Failed",
                details="Certificate files not found after successful certbot run",
            )

        cert_path = self._default_ssl_cert_path()
        key_path = self._default_ssl_key_path()
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)

        # Copy cert and key to platform gateway paths
        shutil.copy2(source_cert, cert_path)
        shutil.copy2(source_key, key_path)

        # Update config
        self.config.read(self.config_file_path)
        if not self.config.has_section("platform_gateway"):
            self.config.add_section("platform_gateway")
        self.config.set("platform_gateway", "ssl_cert", cert_path)
        self.config.set("platform_gateway", "ssl_key", key_path)
        with open(self.config_file_path, "w") as configfile:
            self.config.write(configfile)

        self._restart_platform_gateway()

        return {"ssl_cert": cert_path, "ssl_key": key_path}

    def upload_cert(self, cert_pem: str, key_pem: str, intermediate_pem: str = "") -> Dict[str, str]:
        """Write PEM content to platform gateway certificate files."""
        if not cert_pem.strip() or not key_pem.strip():
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details="Certificate and key PEM content are required",
            )

        cert_path = self._default_ssl_cert_path()
        key_path = self._default_ssl_key_path()
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)

        with open(cert_path, "w") as f:
            f.write(cert_pem.strip() + "\n")
        with open(key_path, "w") as f:
            f.write(key_pem.strip() + "\n")

        if intermediate_pem.strip():
            chain_path = cert_path + ".chain"
            with open(chain_path, "w") as f:
                f.write(intermediate_pem.strip() + "\n")

        # Update config
        self.config.read(self.config_file_path)
        if not self.config.has_section("platform_gateway"):
            self.config.add_section("platform_gateway")
        self.config.set("platform_gateway", "ssl_cert", cert_path)
        self.config.set("platform_gateway", "ssl_key", key_path)
        with open(self.config_file_path, "w") as configfile:
            self.config.write(configfile)

        self._restart_platform_gateway()

        return {"ssl_cert": cert_path, "ssl_key": key_path}

    def _get_platform_brand_title(self) -> str:
        configured = self.config.get("platform_brand", "title", fallback="").strip()
        return configured or DEFAULT_PLATFORM_BRAND_TITLE

    def _get_platform_brand_logo_url(self) -> str:
        configured = self.config.get("platform_brand", "logo_url", fallback="").strip()
        return configured or DEFAULT_PLATFORM_BRAND_LOGO_URL

    def _get_platform_brand_browser_title(self) -> str:
        return self.config.get("platform_brand", "browser_title", fallback=DEFAULT_PLATFORM_BRAND_BROWSER_TITLE).strip()

    def _get_platform_brand_favicon_url(self) -> str:
        configured = self.config.get("platform_brand", "favicon_url", fallback="").strip()
        return configured or DEFAULT_PLATFORM_BRAND_FAVICON_URL

    def _get_platform_brand_apple_touch_icon_url(self) -> str:
        configured = self.config.get("platform_brand", "apple_touch_icon_url", fallback="").strip()
        return configured or DEFAULT_PLATFORM_BRAND_APPLE_TOUCH_ICON_URL

    def _is_valid_brand_logo_url(self, value: str) -> bool:
        candidate = (value or "").strip()
        if not candidate:
            return False
        if candidate.startswith("/"):
            return True
        return candidate.startswith("http://") or candidate.startswith("https://")

    def _write_platform_brand_setting(self, key: str, value: str) -> Dict[str, str]:
        if key not in {"title", "browser_title", "logo_url", "favicon_url", "apple_touch_icon_url"}:
            raise CustomException(
                status_code=400,
                message="Invalid Request",
                details=f"Key:{key} does not exist",
            )

        if not self.config.has_section("platform_brand"):
            self.config.add_section("platform_brand")

        normalized_value = (value or "").strip()
        if key == "title":
            normalized_value = normalized_value or DEFAULT_PLATFORM_BRAND_TITLE
        if key == "browser_title":
            normalized_value = normalized_value
        if key == "logo_url":
            normalized_value = normalized_value or DEFAULT_PLATFORM_BRAND_LOGO_URL
            if not self._is_valid_brand_logo_url(normalized_value):
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details="platform_brand.logo_url must be an absolute http(s) URL or a root-relative path",
                )
        if key == "favicon_url":
            normalized_value = normalized_value or DEFAULT_PLATFORM_BRAND_FAVICON_URL
            if not self._is_valid_brand_logo_url(normalized_value):
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details="platform_brand.favicon_url must be an absolute http(s) URL or a root-relative path",
                )
        if key == "apple_touch_icon_url":
            normalized_value = normalized_value or DEFAULT_PLATFORM_BRAND_APPLE_TOUCH_ICON_URL
            if not self._is_valid_brand_logo_url(normalized_value):
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details="platform_brand.apple_touch_icon_url must be an absolute http(s) URL or a root-relative path",
                )

        self.config.set("platform_brand", key, normalized_value)
        with open(self.config_file_path, "w") as configfile:
            self.config.write(configfile)

        return self.read_section("platform_brand")