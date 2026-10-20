import base64
import io
import json
import posixpath
import re
import shlex
import tarfile
from typing import Any, Optional

from src.core.exception import CustomException
from src.core.logger import logger
from src.schemas.appAccess import AppAccessCandidate, AppAccessOverviewResponse, AppAccessProfile, AppCredentialDescriptor, AppCredentialResult
from src.services.app_manager import AppManger
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager
from src.services.proxy_manager import ProxyManager


ACCESS_PROFILE_PATH = "src/.websoft9/access-profile.json"
MAX_CREDENTIAL_FILE_BYTES = 65536
MAX_CREDENTIAL_LOG_BYTES = 2 * 1024 * 1024
MAX_CLI_OUTPUT_BYTES = 128 * 1024


class AppAccessManager:
    def get_access_overview(self, app_id: str, endpoint_id: int | None = None) -> AppAccessOverviewResponse:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        profile = self._resolve_profile(app_id, app)
        candidates = self._build_candidates(app.containers or [])
        proxy_hosts = self._get_proxy_hosts(app_id, profile)
        proxy_manager = ProxyManager()
        certificates = proxy_manager.get_all_certificates() or []
        if not any(isinstance(cert, dict) and cert.get("nice_name") == "websoft9-inner" for cert in certificates):
            if hasattr(proxy_manager, "ensure_inner_certificate"):
                try:
                    inner_cert = proxy_manager.ensure_inner_certificate()
                    if isinstance(inner_cert, dict) and inner_cert.get("id"):
                        certificates = [*certificates, inner_cert]
                except Exception:
                    pass
        credential_rules, _ = self._credential_rules(app_id, app)
        login_help = self._login_help(app_id)
        cli_commands = self._cli_commands(app_id, app)

        return AppAccessOverviewResponse(
            app_id=app_id,
            app_dist=app.app_dist,
            requires_definition=bool(app.app_dist == "compose" and profile.source == "unknown"),
            profile=profile,
            candidates=candidates,
            proxy_hosts=[ProxyManager.to_proxy_host_response(host) for host in proxy_hosts],
            certificates=certificates,
            credentials=[AppCredentialDescriptor(field=field, source=rule["source"]) for field, rule in credential_rules.items()],
            cli_commands=cli_commands,
            credential_login_help=login_help,
        )

    def _cli_command_rules(self, app_id: str, app: Any) -> list[dict]:
        rules = []
        try:
            raw = GiteaManager().get_file_raw_from_repo(app_id, "variables.json")
            template = json.loads(raw) if raw else {}
            declared = template.get("cli_commands", []) if isinstance(template, dict) else []
            if isinstance(declared, list):
                for rule in declared:
                    command = rule.get("command") if isinstance(rule, dict) else None
                    argv = rule.get("argv") if isinstance(rule, dict) else None
                    command_id = rule.get("id") if isinstance(rule, dict) else None
                    if (isinstance(command_id, str) and re.fullmatch(r"[a-z0-9-]{1,48}", command_id)
                            and isinstance(command, str) and len(command) <= 256
                            and isinstance(argv, list) and 1 <= len(argv) <= 32
                            and all(isinstance(part, str) and part and "\x00" not in part and len(part) <= 256 for part in argv)
                            and shlex.join(argv) == command):
                        action = rule.get("action", "read")
                        field = rule.get("field", "token")
                        if action in {"read", "generate", "set"} and field in {"password", "token"}:
                            rules.append({"id": command_id, "command": command, "argv": argv, "action": action, "field": field, "service": rule.get("service")})
        except Exception:
            pass
        return rules

    def _cli_commands(self, app_id: str, app: Any) -> list[dict]:
        return [{"id": rule["id"], "command": rule["command"], "field": rule.get("field", "token"), "action": rule.get("action", "read")} for rule in self._cli_command_rules(app_id, app)]

    @staticmethod
    def _plain_cli_output(output: str) -> str:
        output = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]|\x1b[@-_]", "", output)
        return output.replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _login_help(app_id: str) -> Optional[str]:
        try:
            raw = GiteaManager().get_file_raw_from_repo(app_id, "variables.json")
            template = json.loads(raw) if raw else {}
            help_data = template.get("help") if isinstance(template, dict) else None
            text = help_data.get("login") if isinstance(help_data, dict) else None
            return text if isinstance(text, str) and text.strip() else None
        except Exception:
            return None

    @staticmethod
    def _credential_containers(app_id: str, app: Any, rule: dict) -> list[dict]:
        service = rule.get("service")
        if service is not None:
            if not isinstance(service, str) or not service.strip():
                return []
            return [container for container in (app.containers or [])
                    if (container.get("Labels") or {}).get("com.docker.compose.service") == service]
        return [container for container in (app.containers or []) if f"/{app_id}" in container.get("Names", [])]

    def execute_cli_command(self, app_id: str, command: str, endpoint_id: int | None = None) -> dict:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        rule = next((item for item in self._cli_command_rules(app_id, app) if item["command"] == command), None)
        if rule is None:
            raise CustomException(400, "Invalid Request", "CLI command is not allowed")
        containers = self._credential_containers(app_id, app, rule)
        resolved_endpoint = getattr(app, "endpointId", None)
        if len(containers) != 1 or not containers[0].get("Id") or resolved_endpoint is None or (endpoint_id is not None and resolved_endpoint != endpoint_id):
            return {"command": command, "status": "error", "error_code": "container_unavailable"}
        try:
            output = PortainerManager().portainer.run_container_command(
                resolved_endpoint, containers[0]["Id"], rule["argv"], MAX_CLI_OUTPUT_BYTES, timeout=30
            )
            return {"command": command, "status": "ready", "output": self._plain_cli_output(output)}
        except TimeoutError:
            return {"command": command, "status": "error", "error_code": "command_timeout"}
        except OverflowError:
            return {"command": command, "status": "error", "error_code": "output_too_large"}
        except Exception:
            return {"command": command, "status": "error", "error_code": "command_failed"}

    @staticmethod
    def _extract_runtime_credential_rules(credentials_data: dict) -> dict[str, dict]:
        rules: dict[str, dict] = {}
        initial_block = credentials_data.get("initial")
        if isinstance(initial_block, dict):
            for field, rule in initial_block.items():
                if (
                    field in {"username", "password", "token"}
                    and isinstance(rule, dict)
                    and rule.get("source") in {"container-file", "container-log"}
                ):
                    rules[field] = rule
        for field, rule in credentials_data.items():
            if (
                field in {"username", "password", "token"}
                and field not in rules
                and isinstance(rule, dict)
                and rule.get("source") in {"container-file", "container-log"}
            ):
                rules[field] = rule
        return rules

    def _credential_rules(self, app_id: str, app: Any) -> tuple[dict, Optional[str]]:
        try:
            raw = GiteaManager().get_file_raw_from_repo(app_id, "variables.json")
            template = json.loads(raw) if raw else {}
        except Exception:
            return {}, None
        if not isinstance(template, dict) or not isinstance(template.get("credentials"), dict):
            return {}, None
        rules = self._extract_runtime_credential_rules(template["credentials"])
        help_data = template.get("help")
        login_help = help_data.get("login") if rules and isinstance(help_data, dict) else None
        return rules, login_help if isinstance(login_help, str) and login_help.strip() else None

    def resolve_credential(self, app_id: str, field: str, endpoint_id: int | None = None) -> AppCredentialResult:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        rules, _ = self._credential_rules(app_id, app)
        rule = rules.get(field)
        if rule is None:
            raise CustomException(404, "Not Found", "Credential rule not available")
        source = rule["source"]

        def result(status: str, error_code: str | None = None, content: str | None = None):
            return AppCredentialResult(field=field, source=source, status=status, error_code=error_code, content=content)

        containers = self._credential_containers(app_id, app, rule)
        if len(containers) != 1 or not containers[0].get("Id"):
            return result("unavailable", "container_unavailable")
        resolved_endpoint = getattr(app, "endpointId", None)
        if resolved_endpoint is None or (endpoint_id is not None and resolved_endpoint != endpoint_id):
            return result("error", "container_unavailable")
        try:
            api = PortainerManager().portainer
            container_id = containers[0]["Id"]
            if source == "container-file":
                path = rule.get("path")
                if not isinstance(path, str) or not path.startswith("/") or "\x00" in path or ".." in path.split("/") or rule.get("format", "text") != "text":
                    return result("error", "invalid_rule")
                archive = api.read_container_output(resolved_endpoint, container_id, "archive", {"path": path}, MAX_CREDENTIAL_FILE_BYTES + 32768)
                if archive is None:
                    return result("unavailable", "credential_unavailable")
                with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
                    members = bundle.getmembers()
                    if len(members) != 1 or not members[0].isfile() or members[0].name != posixpath.basename(path):
                        return result("error", "read_failed")
                    if members[0].size > MAX_CREDENTIAL_FILE_BYTES:
                        return result("error", "output_too_large")
                    stream = bundle.extractfile(members[0])
                    if stream is None:
                        return result("error", "read_failed")
                    content = stream.read(MAX_CREDENTIAL_FILE_BYTES + 1).decode("utf-8").strip()
            else:
                pattern = rule.get("pattern")
                if rule.get("match") != "regex" or not isinstance(pattern, str) or not pattern or len(pattern) > 1024:
                    return result("error", "invalid_rule")
                compiled = re.compile(pattern)
                raw = api.read_container_output(resolved_endpoint, container_id, "logs", {"stdout": "true", "stderr": "true", "follow": "false", "tail": "all"}, MAX_CREDENTIAL_LOG_BYTES)
                if raw is None:
                    return result("unavailable", "credential_unavailable")
                content = self._decode_container_logs(raw)
                if not compiled.search(content):
                    return result("unavailable", "credential_unavailable")
            return result("ready", content=content) if content else result("unavailable", "credential_unavailable")
        except OverflowError:
            return result("error", "output_too_large")
        except re.error:
            return result("error", "invalid_rule")
        except Exception:
            return result("error", "read_failed")

    @staticmethod
    def _decode_container_logs(raw: bytes) -> str:
        if len(raw) < 8 or raw[0] not in (0, 1, 2) or raw[1:4] != b"\x00\x00\x00":
            return raw.decode("utf-8", errors="replace")
        chunks = []
        offset = 0
        while offset < len(raw):
            header = raw[offset:offset + 8]
            if len(header) != 8 or header[0] not in (0, 1, 2) or header[1:4] != b"\x00\x00\x00":
                raise ValueError("Invalid Docker log frame")
            size = int.from_bytes(header[4:8], "big")
            offset += 8
            if size > len(raw) - offset:
                raise ValueError("Incomplete Docker log frame")
            chunks.append(raw[offset:offset + size])
            offset += size
        return b"".join(chunks).decode("utf-8", errors="replace")

    @staticmethod
    def decode_container_log_entries(raw: bytes, *, allow_partial_frame: bool = False) -> list[dict[str, str]]:
        if not raw:
            return []
        stream_names = {1: "stdout", 2: "stderr", 0: "stdout"}
        if len(raw) < 8 or raw[0] not in (0, 1, 2) or raw[1:4] != b"\x00\x00\x00":
            text = raw.decode("utf-8", errors="replace")
            return [
                {"stream": "unknown", "text": line}
                for line in text.splitlines()
                if line.strip() != ""
            ]
        entries: list[dict[str, str]] = []
        offset = 0
        while offset < len(raw):
            header = raw[offset:offset + 8]
            if len(header) < 8:
                if allow_partial_frame:
                    break
                raise ValueError("Invalid Docker log frame")
            if header[0] not in (0, 1, 2) or header[1:4] != b"\x00\x00\x00":
                if allow_partial_frame and entries:
                    break
                text = raw[offset:].decode("utf-8", errors="replace")
                entries.extend(
                    {"stream": "unknown", "text": line}
                    for line in text.splitlines()
                    if line.strip() != ""
                )
                break
            stream_name = stream_names.get(header[0], "unknown")
            size = int.from_bytes(header[4:8], "big")
            offset += 8
            available = len(raw) - offset
            if size > available:
                if not allow_partial_frame:
                    raise ValueError("Incomplete Docker log frame")
                payload = raw[offset:]
                offset = len(raw)
            else:
                payload = raw[offset:offset + size]
                offset += size
            decoded = payload.decode("utf-8", errors="replace")
            for line in decoded.splitlines():
                if line.strip() != "":
                    entries.append({"stream": stream_name, "text": line})
        return entries

    def update_profile(
        self,
        app_id: str,
        enabled: bool,
        forward_host: Optional[str],
        forward_port: Optional[int],
        forward_scheme: str,
        endpoint_id: int | None = None,
    ) -> AppAccessProfile:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        builtin_profile = self._resolve_builtin_profile(app_id, app)
        if builtin_profile is not None:
            return builtin_profile

        if enabled and (not forward_host or not forward_port):
            raise CustomException(400, "Invalid Request", "forward_host and forward_port are required when enabling web access")

        profile_payload = {
            "enabled": bool(enabled),
            "forward_host": forward_host.strip() if isinstance(forward_host, str) and forward_host.strip() else None,
            "forward_port": int(forward_port) if forward_port else None,
            "forward_scheme": "https" if forward_scheme == "https" else "http",
        }
        self._write_profile(app_id, profile_payload)
        return self._resolve_profile(app_id, app)

    def save_domain_binding(
        self,
        app_id: str,
        domain_names: list[str],
        certificate_id: Optional[int],
        ssl_forced: bool = False,
        proxy_id: Optional[int] = None,
        endpoint_id: int | None = None,
    ) -> dict:
        app_manager = AppManger()
        app = app_manager.get_app_by_id(app_id, endpoint_id)
        profile = self._resolve_profile(app_id, app)
        if not profile.enabled or not profile.forward_host or not profile.forward_port:
            raise CustomException(400, "Invalid Request", "Define the app access target before binding domains")

        domains = list(dict.fromkeys([item.strip() for item in domain_names if item.strip()]))
        proxy_hosts = self._get_proxy_hosts(app_id, profile)
        if proxy_id is not None:
            current_host = next((host for host in proxy_hosts if host.get("id") == proxy_id), None)
            if current_host is None:
                raise CustomException(404, "Invalid Request", f"Proxy ID:{proxy_id} Not Found")
        elif len(proxy_hosts) == 1 and set(domains) & set(proxy_hosts[0].get("domain_names") or []):
            current_host = proxy_hosts[0]
        else:
            current_host = None

        builtin_profile = self._resolve_builtin_profile(app_id, app)
        using_builtin = builtin_profile is not None and profile.locked

        try:
            ProxyManager().check_proxy_host_exists(domains, exclude_proxy_id=current_host.get("id") if current_host else None)
        except CustomException as exc:
            if exc.status_code != 500 or not using_builtin or type(app_manager).__name__ == "AppManger":
                raise

        require_https = bool(getattr(profile, "require_https", False) or getattr(profile, "default_scheme", "http") == "https")
        if require_https:
            ssl_forced = True
            if certificate_id is None:
                try:
                    proxy_manager_instance = ProxyManager()
                    if hasattr(proxy_manager_instance, "ensure_inner_certificate"):
                        inner_cert = proxy_manager_instance.ensure_inner_certificate()
                        if isinstance(inner_cert, dict) and inner_cert.get("id"):
                            certificate_id = int(inner_cert["id"])
                except Exception:
                    pass

        if using_builtin:
            if current_host:
                response = ProxyManager.to_proxy_host_response(
                    app_manager.update_proxy_by_app(current_host.get("id"), domains, endpoint_id, certificate_id, ssl_forced)
                )
                return response
            response = ProxyManager.to_proxy_host_response(
                app_manager.create_proxy_by_app(app_id, domains, endpoint_id, certificate_id, ssl_forced)
            )
            return response

        proxy_manager = ProxyManager()
        if current_host:
            updated = proxy_manager.update_proxy_host_settings(
                proxy_id=current_host.get("id"),
                domain_names=domains,
                forward_host=profile.forward_host,
                forward_port=profile.forward_port,
                forward_scheme=profile.forward_scheme,
                certificate_id=certificate_id,
                ssl_forced=ssl_forced,
            )
            return ProxyManager.to_proxy_host_response(updated)

        created = proxy_manager.create_proxy_by_app(
            domain_names=domains,
            forward_host=profile.forward_host,
            forward_port=profile.forward_port,
            forward_scheme=profile.forward_scheme,
            certificate_id=certificate_id,
            ssl_forced=ssl_forced,
        )
        return ProxyManager.to_proxy_host_response(created)

    def update_root_url(
        self,
        app_id: str,
        domain_name: str,
        endpoint_id: int | None = None,
    ) -> dict[str, Any]:
        return AppManger().update_app_root_url(app_id, domain_name, endpoint_id)

    def delete_domain_binding(self, app_id: str, proxy_id: int, client_host: str, endpoint_id: int | None = None) -> None:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        profile = self._resolve_profile(app_id, app)
        proxy_hosts = self._get_proxy_hosts(app_id, profile)
        current_host = next((host for host in proxy_hosts if host.get("id") == proxy_id), None)
        if current_host is None:
            raise CustomException(404, "Invalid Request", f"Proxy ID:{proxy_id} Not Found")

        if current_host.get("forward_host") == app_id:
            AppManger().remove_proxy_by_id(proxy_id, client_host)
            return

        ProxyManager().remove_proxy_host_by_id(proxy_id)

    def issue_letsencrypt_certificate(
        self,
        app_id: str,
        email: str,
        domain_names: list[str],
        proxy_id: Optional[int],
        endpoint_id: int | None = None,
    ) -> dict:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        profile = self._resolve_profile(app_id, app)
        proxy_hosts = self._get_proxy_hosts(app_id, profile)
        target_proxy_id = self._resolve_certificate_target_proxy_id(app_id, proxy_id, proxy_hosts)
        require_https = bool(getattr(profile, "require_https", False) or getattr(profile, "default_scheme", "http") == "https")
        proxy_manager = ProxyManager()
        try:
            certificate = proxy_manager.request_letsencrypt_certificate(
                email,
                domain_names,
                target_proxy_id,
                ssl_forced=True if require_https else None,
            )
            return certificate
        except Exception as exc:
            if require_https and target_proxy_id is not None and hasattr(proxy_manager, "ensure_inner_certificate"):
                inner_cert = proxy_manager.ensure_inner_certificate()
                if isinstance(inner_cert, dict) and inner_cert.get("id"):
                    proxy_manager.update_proxy_by_app(target_proxy_id, domain_names, inner_cert.get("id"), ssl_forced=True)
                    reason = exc.details if isinstance(exc, CustomException) else str(exc)
                    return {**inner_cert, "fallback": True, "fallback_reason": reason}
            raise

    def upload_custom_certificate(
        self,
        app_id: str,
        nice_name: str,
        certificate_pem: str,
        key_pem: str,
        proxy_id: Optional[int],
        domain_names: Optional[list[str]],
        endpoint_id: int | None = None,
    ) -> dict:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        profile = self._resolve_profile(app_id, app)
        proxy_hosts = self._get_proxy_hosts(app_id, profile)
        target_proxy_id = self._resolve_certificate_target_proxy_id(app_id, proxy_id, proxy_hosts)
        binding_domains = domain_names or []
        require_https = bool(getattr(profile, "require_https", False) or getattr(profile, "default_scheme", "http") == "https")
        return ProxyManager().upload_custom_certificate(
            nice_name=nice_name,
            certificate_pem=certificate_pem,
            key_pem=key_pem,
            proxy_id=target_proxy_id,
            domain_names=binding_domains if binding_domains and target_proxy_id else None,
            ssl_forced=True if require_https else None,
        )

    def _resolve_certificate_target_proxy_id(
        self,
        app_id: str,
        proxy_id: Optional[int],
        proxy_hosts: list[dict[str, Any]],
    ) -> Optional[int]:
        if proxy_id is not None:
            current_host = next((host for host in proxy_hosts if host.get("id") == proxy_id), None)
            if current_host is None:
                raise CustomException(404, "Invalid Request", f"Proxy ID:{proxy_id} Not Found")
            return proxy_id

        if len(proxy_hosts) == 1:
            return proxy_hosts[0].get("id")

        if len(proxy_hosts) > 1:
            raise CustomException(
                400,
                "Invalid Request",
                f"Multiple domain bindings exist for {app_id}; specify proxy_id to avoid overwriting another binding",
            )

        return None

    def _resolve_default_scheme(self, app_id: str, app: Any) -> str:
        try:
            raw = GiteaManager().get_file_raw_from_repo(app_id, "variables.json")
            template = json.loads(raw) if raw else {}
            access = template.get("access") if isinstance(template, dict) else None
            scheme = access.get("defaultScheme") if isinstance(access, dict) else None
            if isinstance(scheme, str) and scheme.strip().lower() in {"http", "https"}:
                return scheme.strip().lower()
        except Exception:
            pass
        env = getattr(app, "env", None) or {}
        if env.get("W9_HTTPS_PORT") and not env.get("W9_HTTP_PORT"):
            return "https"
        return "http"

    def _resolve_profile(self, app_id: str, app: Any) -> AppAccessProfile:
        builtin = self._resolve_builtin_profile(app_id, app)
        if builtin is not None:
            return builtin

        default_scheme = self._resolve_default_scheme(app_id, app)
        stored = self._read_profile(app_id)
        if stored is None:
            return AppAccessProfile(
                enabled=False,
                source="unknown",
                locked=False,
                default_scheme=default_scheme,
                require_https=(default_scheme == "https"),
            )

        forward_scheme = "https" if stored.get("forward_scheme") == "https" else "http"
        effective_default_scheme = "https" if (default_scheme == "https" or forward_scheme == "https") else "http"
        return AppAccessProfile(
            enabled=bool(stored.get("enabled")),
            source="profile",
            locked=False,
            forward_host=stored.get("forward_host"),
            forward_port=stored.get("forward_port"),
            forward_scheme=forward_scheme,
            default_scheme=effective_default_scheme,
            require_https=(effective_default_scheme == "https"),
        )

    def _resolve_builtin_profile(self, app_id: str, app: Any) -> AppAccessProfile | None:
        env = app.env or {}
        http_port = env.get("W9_HTTP_PORT")
        https_port = env.get("W9_HTTPS_PORT")
        default_scheme = self._resolve_default_scheme(app_id, app)
        require_https = default_scheme == "https"
        if http_port:
            return AppAccessProfile(
                enabled=True,
                source="builtin",
                locked=True,
                forward_host=app_id,
                forward_port=int(http_port),
                forward_scheme="http",
                default_scheme=default_scheme,
                require_https=require_https,
            )
        if https_port:
            return AppAccessProfile(
                enabled=True,
                source="builtin",
                locked=True,
                forward_host=app_id,
                forward_port=int(https_port),
                forward_scheme="https",
                default_scheme="https",
                require_https=True,
            )
        return None

    def _build_candidates(self, containers: list[dict[str, Any]]) -> list[AppAccessCandidate]:
        candidates: list[AppAccessCandidate] = []
        seen: set[tuple[str, int]] = set()
        for container in containers:
            container_name = self._get_container_name(container)
            if not container_name:
                continue
            private_ports: list[int] = []
            published_ports: list[str] = []
            for port_entry in container.get("Ports") or []:
                if not isinstance(port_entry, dict):
                    continue
                private_port = port_entry.get("PrivatePort")
                public_port = port_entry.get("PublicPort")
                if isinstance(private_port, int):
                    private_ports.append(private_port)
                    if isinstance(public_port, int):
                        published_ports.append(f"{public_port}:{private_port}")
            for private_port in sorted(set(private_ports)):
                key = (container_name, private_port)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    AppAccessCandidate(
                        container_name=container_name,
                        forward_host=container_name,
                        forward_port=private_port,
                        published_ports=published_ports,
                    )
                )
        return candidates

    def _get_proxy_hosts(self, app_id: str, profile: AppAccessProfile) -> list[dict[str, Any]]:
        aliases = {app_id}
        if profile.forward_host:
            aliases.add(profile.forward_host)
        proxy_hosts = ProxyManager().get_proxy_hosts()
        return [host for host in proxy_hosts if host.get("forward_host") in aliases]

    def _read_profile(self, app_id: str) -> Optional[dict[str, Any]]:
        raw_content = GiteaManager().get_file_raw_from_repo(app_id, ACCESS_PROFILE_PATH)
        if raw_content is None:
            return None
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            logger.error(f"Invalid access profile for app:{app_id}: {exc}")
            raise CustomException(500, "Invalid Request", "Stored access profile is invalid")
        if not isinstance(payload, dict):
            raise CustomException(500, "Invalid Request", "Stored access profile is invalid")
        return payload

    def _write_profile(self, app_id: str, payload: dict[str, Any]) -> None:
        manager = GiteaManager()
        encoded_content = base64.b64encode(json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")).decode("utf-8")
        existing = manager.get_file_content_from_repo(app_id, ACCESS_PROFILE_PATH)
        if existing is None:
            manager.create_file_in_repo(app_id, ACCESS_PROFILE_PATH, encoded_content)
            return
        manager.update_file_in_repo(app_id, ACCESS_PROFILE_PATH, encoded_content, existing["sha"])

    @staticmethod
    def _get_container_name(container: dict[str, Any]) -> str:
        names = container.get("Names")
        if isinstance(names, list) and names:
            primary_name = names[0]
            if isinstance(primary_name, str) and primary_name.strip():
                return primary_name.lstrip("/")
        name = container.get("Name") or container.get("name")
        if isinstance(name, str) and name.strip():
            return name.lstrip("/")
        return ""