from __future__ import annotations

from typing import Any

import click

from src.cli.cli_output import CLIError, run_cli_action


@click.group(name="gateway")
def gateway_group():
    """Manage application reverse proxy routing and SSL certificates.

    These commands manage application access, not the platform gateway process.
    """


@gateway_group.group(name="proxy")
def gateway_proxy_group():
    """Inspect and update application reverse proxy bindings."""


@gateway_group.group(name="cert")
def gateway_cert_group():
    """Inspect and request SSL certificates in Nginx Proxy Manager."""


@gateway_proxy_group.command(name="list")
@click.option("--app-id", help="Filter proxy bindings for a specific application.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID when inspecting an application.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_proxies_command(app_id: str | None, endpoint_id: int | None, as_json: bool) -> None:
    """List reverse proxy bindings or inspect an application's access overview."""
    def action() -> dict[str, Any]:
        from src.services.app_access_manager import AppAccessManager
        from src.services.proxy_manager import ProxyManager

        if app_id:
            overview = AppAccessManager().get_access_overview(app_id, endpoint_id)
            return overview.model_dump()

        hosts = ProxyManager().get_proxy_hosts() or []
        items = [
            {
                "id": host.get("id"),
                "domain_names": host.get("domain_names") or [],
                "forward_scheme": host.get("forward_scheme"),
                "forward_host": host.get("forward_host"),
                "forward_port": host.get("forward_port"),
                "certificate_id": host.get("certificate_id"),
                "ssl_forced": bool(host.get("ssl_forced", False)),
                "enabled": bool(host.get("enabled", True)),
            }
            for host in hosts
            if isinstance(host, dict)
        ]
        return {
            "items": items,
            "total": len(items),
        }

    def render_text(payload: dict[str, Any]) -> str:
        if "app_id" in payload:
            hosts = payload.get("proxy_hosts") or []
            profile = payload.get("profile") or {}
            lines = [
                f"App Access: {payload.get('app_id')} (enabled={profile.get('enabled')} target={profile.get('forward_scheme')}://{profile.get('forward_host')}:{profile.get('forward_port')})"
            ]
            for host in hosts:
                lines.append(f"- proxy_id={host.get('proxy_id')} domains={', '.join(host.get('domain_names') or [])} ssl_forced={host.get('ssl_forced')}")
            return "\n".join(lines)
        items = payload.get("items") or []
        if not items:
            return "No proxy hosts configured."
        lines = [f"Proxy Hosts ({len(items)}):"]
        for item in items:
            lines.append(
                f"- id={item.get('id')} domains={', '.join(item.get('domain_names') or [])} "
                f"-> {item.get('forward_scheme')}://{item.get('forward_host')}:{item.get('forward_port')}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@gateway_proxy_group.command(name="bind")
@click.argument("app_id")
@click.option("--domain", "domains", multiple=True, required=True, help="Domain name to bind (repeatable).")
@click.option("--cert-id", "certificate_id", type=click.IntRange(min=1), default=None, help="Certificate ID in Nginx Proxy Manager.")
@click.option("--ssl-forced/--no-ssl-forced", default=False, show_default=True, help="Force HTTPS redirection.")
@click.option("--proxy-id", type=click.IntRange(min=1), default=None, help="Existing proxy host ID to update.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), default=None, help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm binding domain(s) to the application.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def bind_proxy_command(
    app_id: str,
    domains: tuple[str, ...],
    certificate_id: int | None,
    ssl_forced: bool,
    proxy_id: int | None,
    endpoint_id: int | None,
    yes: bool,
    as_json: bool,
) -> None:
    """Bind one or more domain names to an application's reverse proxy."""
    def action() -> dict[str, Any]:
        from src.services.app_access_manager import AppAccessManager

        domain_list = [d.strip() for d in domains if d and d.strip()]
        if not domain_list:
            raise CLIError("INVALID_ARGUMENT", "At least one non-empty --domain is required", exit_code=2)
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Binding domains {domain_list} to '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "domains": domain_list},
                )
            if not click.confirm(f"Bind domain(s) {domain_list} to application '{app_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        result = AppAccessManager().save_domain_binding(
            app_id=app_id,
            domain_names=domain_list,
            certificate_id=certificate_id,
            ssl_forced=ssl_forced,
            proxy_id=proxy_id,
            endpoint_id=endpoint_id,
        )
        return {
            "app_id": app_id,
            "binding": result,
        }

    def render_text(payload: dict[str, Any]) -> str:
        binding = payload.get("binding") or {}
        return f"Bound domains {', '.join(binding.get('domain_names') or [])} to '{payload.get('app_id')}' (proxy_id={binding.get('proxy_id')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@gateway_proxy_group.command(name="set-target")
@click.argument("app_id")
@click.option("--enabled/--disabled", default=True, show_default=True, help="Enable or disable web access profile.")
@click.option("--host", "forward_host", default=None, help="Forward container/service host.")
@click.option("--port", "forward_port", type=click.IntRange(min=1, max=65535), default=None, help="Forward container port.")
@click.option("--scheme", "forward_scheme", type=click.Choice(["http", "https"], case_sensitive=False), default="http", show_default=True, help="Forward scheme.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), default=None, help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm updating access target.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def set_proxy_target_command(
    app_id: str,
    enabled: bool,
    forward_host: str | None,
    forward_port: int | None,
    forward_scheme: str,
    endpoint_id: int | None,
    yes: bool,
    as_json: bool,
) -> None:
    """Update the forwarding target profile for a custom Compose application."""
    def action() -> dict[str, Any]:
        from src.services.app_access_manager import AppAccessManager

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Updating access target for '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "enabled": enabled, "forward_host": forward_host, "forward_port": forward_port},
                )
            if not click.confirm(f"Update access target for '{app_id}' to {forward_scheme}://{forward_host}:{forward_port} (enabled={enabled})?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        profile = AppAccessManager().update_profile(
            app_id=app_id,
            enabled=enabled,
            forward_host=forward_host,
            forward_port=forward_port,
            forward_scheme=forward_scheme.lower(),
            endpoint_id=endpoint_id,
        )
        return {
            "app_id": app_id,
            "profile": profile.model_dump(),
        }

    def render_text(payload: dict[str, Any]) -> str:
        prof = payload.get("profile") or {}
        return f"Updated access target for '{payload.get('app_id')}': {prof.get('forward_scheme')}://{prof.get('forward_host')}:{prof.get('forward_port')} (enabled={prof.get('enabled')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@gateway_proxy_group.command(name="set-root-url")
@click.argument("app_id")
@click.option("--domain", "domain_name", required=True, help="Primary domain name or root URL to apply.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), default=None, help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm updating root URL.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def set_root_url_command(app_id: str, domain_name: str, endpoint_id: int | None, yes: bool, as_json: bool) -> None:
    """Synchronize W9_URL with the selected primary domain for an application."""
    def action() -> dict[str, Any]:
        from src.services.app_access_manager import AppAccessManager

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Updating root URL for '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "domain": domain_name},
                )
            if not click.confirm(f"Update root URL of '{app_id}' to '{domain_name}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        return AppAccessManager().update_root_url(app_id, domain_name.strip(), endpoint_id)

    def render_text(payload: dict[str, Any]) -> str:
        return f"Updated root URL for '{app_id}' -> {domain_name}."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@gateway_proxy_group.command(name="delete")
@click.argument("app_id")
@click.option("--proxy-id", required=True, type=click.IntRange(min=1), help="Proxy host ID to remove.")
@click.option("--client-host", default="127.0.0.1", show_default=True, help="Fallback host IP when last domain is removed.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), default=None, help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm deleting proxy domain binding.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def delete_proxy_command(app_id: str, proxy_id: int, client_host: str, endpoint_id: int | None, yes: bool, as_json: bool) -> None:
    """Delete a reverse proxy domain binding from an application."""
    def action() -> dict[str, Any]:
        from src.services.app_access_manager import AppAccessManager

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Deleting proxy binding {proxy_id} for '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "proxy_id": proxy_id},
                )
            if not click.confirm(f"Delete proxy binding ID {proxy_id} for application '{app_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        AppAccessManager().delete_domain_binding(app_id, proxy_id, client_host, endpoint_id)
        return {
            "app_id": app_id,
            "deleted_proxy_id": proxy_id,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Deleted proxy binding {payload.get('deleted_proxy_id')} for '{payload.get('app_id')}'."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@gateway_cert_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_certs_command(as_json: bool) -> None:
    """List SSL certificates managed by Nginx Proxy Manager."""
    def action() -> dict[str, Any]:
        from src.services.proxy_manager import ProxyManager

        certs = ProxyManager().get_all_certificates() or []
        items = [
            {
                "id": cert.get("id"),
                "nice_name": cert.get("nice_name"),
                "provider": cert.get("provider"),
                "domain_names": cert.get("domain_names") or [],
                "expires_on": cert.get("expires_on"),
                "created_on": cert.get("created_on"),
            }
            for cert in certs
            if isinstance(cert, dict)
        ]
        return {
            "items": items,
            "total": len(items),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No SSL certificates found."
        lines = [f"SSL Certificates ({len(items)}):"]
        for item in items:
            lines.append(
                f"- id={item.get('id')} name={item.get('nice_name')} provider={item.get('provider')} "
                f"domains={', '.join(item.get('domain_names') or [])} expires={item.get('expires_on') or '-'}"
            )
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@gateway_cert_group.command(name="issue-letsencrypt")
@click.argument("app_id")
@click.option("--domain", "domains", multiple=True, required=True, help="Domain name for Let's Encrypt certificate (repeatable).")
@click.option("--email", required=True, help="Contact email for Let's Encrypt registration.")
@click.option("--proxy-id", type=click.IntRange(min=1), default=None, help="Optional proxy host ID to bind the issued certificate.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), default=None, help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm requesting Let's Encrypt certificate.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def issue_letsencrypt_command(
    app_id: str,
    domains: tuple[str, ...],
    email: str,
    proxy_id: int | None,
    endpoint_id: int | None,
    yes: bool,
    as_json: bool,
) -> None:
    """Issue a Let's Encrypt SSL certificate for an application's domain(s)."""
    def action() -> dict[str, Any]:
        from src.services.app_access_manager import AppAccessManager

        domain_list = [d.strip() for d in domains if d and d.strip()]
        if not domain_list:
            raise CLIError("INVALID_ARGUMENT", "At least one non-empty --domain is required", exit_code=2)
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Issuing Let's Encrypt certificate for {domain_list} requires --yes confirmation",
                    details={"app_id": app_id, "domains": domain_list, "email": email},
                )
            if not click.confirm(f"Request Let's Encrypt certificate for {domain_list} (app={app_id}, email={email})?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        cert = AppAccessManager().issue_letsencrypt_certificate(
            app_id=app_id,
            email=email.strip(),
            domain_names=domain_list,
            proxy_id=proxy_id,
            endpoint_id=endpoint_id,
        )
        return {
            "app_id": app_id,
            "certificate": {
                "id": cert.get("id") if isinstance(cert, dict) else None,
                "nice_name": cert.get("nice_name") if isinstance(cert, dict) else None,
                "domain_names": cert.get("domain_names") if isinstance(cert, dict) else domain_list,
                "expires_on": cert.get("expires_on") if isinstance(cert, dict) else None,
            },
        }

    def render_text(payload: dict[str, Any]) -> str:
        cert = payload.get("certificate") or {}
        return f"Issued Let's Encrypt certificate id={cert.get('id')} for {', '.join(cert.get('domain_names') or [])}."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
