import base64
import json
from typing import Any, Optional

from src.core.exception import CustomException
from src.core.logger import logger
from src.schemas.appAccess import AppAccessCandidate, AppAccessOverviewResponse, AppAccessProfile
from src.services.app_manager import AppManger
from src.services.gitea_manager import GiteaManager
from src.services.proxy_manager import ProxyManager


ACCESS_PROFILE_PATH = "src/.websoft9/access-profile.json"


class AppAccessManager:
    def get_access_overview(self, app_id: str, endpoint_id: int | None = None) -> AppAccessOverviewResponse:
        app = AppManger().get_app_by_id(app_id, endpoint_id)
        profile = self._resolve_profile(app_id, app)
        candidates = self._build_candidates(app.containers or [])
        proxy_hosts = self._get_proxy_hosts(app_id, profile)
        certificates = ProxyManager().get_all_certificates()

        return AppAccessOverviewResponse(
            app_id=app_id,
            app_dist=app.app_dist,
            requires_definition=bool(app.app_dist == "compose" and profile.source == "unknown"),
            profile=profile,
            candidates=candidates,
            proxy_hosts=[ProxyManager.to_proxy_host_response(host) for host in proxy_hosts],
            certificates=certificates,
        )

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
        current_host = next((host for host in proxy_hosts if host.get("id") == proxy_id), None) if proxy_id is not None else None

        if proxy_id is not None and current_host is None:
            raise CustomException(404, "Invalid Request", f"Proxy ID:{proxy_id} Not Found")

        builtin_profile = self._resolve_builtin_profile(app_id, app)
        using_builtin = builtin_profile is not None and profile.locked

        if using_builtin:
            if current_host:
                return ProxyManager.to_proxy_host_response(
                    app_manager.update_proxy_by_app(current_host.get("id"), domains, endpoint_id, certificate_id, ssl_forced)
                )
            return ProxyManager.to_proxy_host_response(
                app_manager.create_proxy_by_app(app_id, domains, endpoint_id, certificate_id, ssl_forced)
            )

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

    def update_root_url(
        self,
        app_id: str,
        domain_name: str,
        endpoint_id: int | None = None,
    ) -> dict[str, Any]:
        return AppManger().update_app_root_url(app_id, domain_name, endpoint_id)
        return ProxyManager.to_proxy_host_response(created)

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
        return ProxyManager().request_letsencrypt_certificate(email, domain_names, target_proxy_id)

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
        return ProxyManager().upload_custom_certificate(
            nice_name=nice_name,
            certificate_pem=certificate_pem,
            key_pem=key_pem,
            proxy_id=target_proxy_id,
            domain_names=binding_domains if binding_domains and target_proxy_id else None,
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

    def _resolve_profile(self, app_id: str, app: Any) -> AppAccessProfile:
        builtin = self._resolve_builtin_profile(app_id, app)
        if builtin is not None:
            return builtin

        stored = self._read_profile(app_id)
        if stored is None:
            return AppAccessProfile(enabled=False, source="unknown", locked=False)

        return AppAccessProfile(
            enabled=bool(stored.get("enabled")),
            source="profile",
            locked=False,
            forward_host=stored.get("forward_host"),
            forward_port=stored.get("forward_port"),
            forward_scheme="https" if stored.get("forward_scheme") == "https" else "http",
        )

    def _resolve_builtin_profile(self, app_id: str, app: Any) -> AppAccessProfile | None:
        env = app.env or {}
        http_port = env.get("W9_HTTP_PORT")
        https_port = env.get("W9_HTTPS_PORT")
        if http_port:
            return AppAccessProfile(
                enabled=True,
                source="builtin",
                locked=True,
                forward_host=app_id,
                forward_port=int(http_port),
                forward_scheme="http",
            )
        if https_port:
            return AppAccessProfile(
                enabled=True,
                source="builtin",
                locked=True,
                forward_host=app_id,
                forward_port=int(https_port),
                forward_scheme="https",
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