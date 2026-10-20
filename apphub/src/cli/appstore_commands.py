from __future__ import annotations

from typing import Any

import click

from src.cli.cli_output import CLIError, run_cli_action


def _summarize_store_app(item: dict[str, Any], *, detailed: bool = False) -> dict[str, Any]:
    distributions = item.get("distribution") or []
    editions = [
        {
            "dist": dist.get("key"),
            "versions": list(dist.get("value") or []),
        }
        for dist in distributions
        if isinstance(dist, dict) and dist.get("key")
    ]
    summary = {
        "key": item.get("key"),
        "trademark": item.get("trademark") or item.get("key"),
        "summary": item.get("summary") or item.get("overview") or None,
        "origin": item.get("app_origin") or "official",
        "is_web_app": bool(item.get("is_web_app")),
        "default_scheme": item.get("default_scheme") or "http",
        "vm_memory": item.get("vmmemory"),
        "editions": editions,
    }
    if detailed:
        summary.update(
            {
                "overview": item.get("overview"),
                "description": item.get("description"),
                "settings": dict(item.get("settings") or {}),
                "profiles": dict(item.get("profiles") or {}),
                "help": dict(item.get("help") or {}) if isinstance(item.get("help"), dict) else None,
            }
        )
    return summary


def _load_store_apps(locale: str, source: str) -> tuple[list[dict[str, Any]], list[str]]:
    from src.services.app_manager import AppManger
    from src.services.local_app_store import get_local_app_store_apps

    normalized_source = source.lower()
    apps: list[dict[str, Any]] = []
    warnings: list[str] = []

    if normalized_source in {"all", "official"}:
        try:
            official_apps = AppManger().get_available_apps(locale)
            for item in official_apps or []:
                if isinstance(item, dict):
                    copied = dict(item)
                    copied.setdefault("app_origin", "official")
                    apps.append(copied)
        except Exception as exc:
            if normalized_source == "official":
                raise
            warnings.append(f"official_catalog_unavailable: {exc}")

    if normalized_source in {"all", "local"}:
        try:
            local_apps = get_local_app_store_apps()
            for item in local_apps or []:
                if isinstance(item, dict):
                    copied = dict(item)
                    copied.setdefault("app_origin", "local")
                    apps.append(copied)
        except Exception as exc:
            if normalized_source == "local":
                raise CLIError("DEPENDENCY_UNAVAILABLE", str(exc)) from exc
            warnings.append(f"local_catalog_unavailable: {exc}")

    return apps, warnings


def register_appstore_commands(appstore_group: click.Group) -> None:
    @appstore_group.command(name="search")
    @click.argument("query", required=False, default="")
    @click.option("--locale", type=click.Choice(["en", "zh"], case_sensitive=False), default="en", show_default=True, help="Catalog language.")
    @click.option(
        "--source",
        type=click.Choice(["all", "official", "local"], case_sensitive=False),
        default="all",
        show_default=True,
        help="Catalog source to search.",
    )
    @click.option("--limit", type=click.IntRange(min=1, max=500), default=50, show_default=True, help="Maximum matching templates to return.")
    @click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
    def appstore_search(query: str, locale: str, source: str, limit: int, as_json: bool) -> None:
        """Search available application templates in the App Store."""
        def action() -> dict[str, Any]:
            apps, warnings = _load_store_apps(locale.lower(), source.lower())
            needle = str(query or "").strip().lower()
            matched: list[dict[str, Any]] = []
            for item in apps:
                haystack = " ".join(
                    str(item.get(field) or "")
                    for field in ("key", "trademark", "summary", "overview", "description")
                ).lower()
                if not needle or needle in haystack:
                    matched.append(_summarize_store_app(item, detailed=False))
            matched.sort(key=lambda entry: (0 if str(entry.get("key") or "").lower() == needle else 1, str(entry.get("key") or "")))
            total = len(matched)
            return {
                "query": query,
                "items": matched[:limit],
                "total": total,
                "limit": limit,
                "warnings": warnings,
            }

        def render_text(payload: dict[str, Any]) -> str:
            items = payload.get("items") or []
            if not items:
                return f"No App Store templates matched '{payload.get('query') or ''}'."
            lines = [f"App Store templates ({len(items)}/{payload.get('total', len(items))}):"]
            for item in items:
                versions = [ver for ed in (item.get("editions") or []) for ver in (ed.get("versions") or [])]
                ver_text = ", ".join(versions[:5]) if versions else "-"
                lines.append(f"- {item.get('key')} ({item.get('trademark')}) [{item.get('origin')}] versions={ver_text}")
            return "\n".join(lines)

        run_cli_action(action, as_json=as_json, text_renderer=render_text)

    @appstore_group.command(name="info")
    @click.argument("app_key")
    @click.option("--locale", type=click.Choice(["en", "zh"], case_sensitive=False), default="en", show_default=True, help="Catalog language.")
    @click.option(
        "--source",
        type=click.Choice(["all", "official", "local"], case_sensitive=False),
        default="all",
        show_default=True,
        help="Catalog source to inspect.",
    )
    @click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
    def appstore_info(app_key: str, locale: str, source: str, as_json: bool) -> None:
        """Inspect template versions, required settings, profiles, and memory requirements."""
        def action() -> dict[str, Any]:
            apps, warnings = _load_store_apps(locale.lower(), source.lower())
            normalized_key = app_key.strip().lower()
            target = next((item for item in apps if str(item.get("key") or "").strip().lower() == normalized_key), None)
            if target is None:
                raise CLIError("APP_TEMPLATE_NOT_FOUND", f"Application template '{app_key}' not found", details={"app_key": app_key})
            return {
                "template": _summarize_store_app(target, detailed=True),
                "warnings": warnings,
            }

        def render_text(payload: dict[str, Any]) -> str:
            tpl = payload.get("template") or {}
            editions = tpl.get("editions") or []
            settings = tpl.get("settings") or {}
            profiles = tpl.get("profiles") or {}
            lines = [
                f"Template: {tpl.get('key')} ({tpl.get('trademark')})",
                f"Origin: {tpl.get('origin')}",
                f"Web App: {tpl.get('is_web_app')} (scheme={tpl.get('default_scheme')})",
                f"Min Memory: {tpl.get('vm_memory') or '-'}",
                f"Editions: {editions}",
                f"Settings Keys: {', '.join(sorted(settings.keys())) if settings else '-'}",
                f"Profiles: {', '.join(sorted(profiles.keys())) if profiles else '-'}",
            ]
            if tpl.get("summary"):
                lines.append(f"Summary: {tpl.get('summary')}")
            return "\n".join(lines)

        run_cli_action(action, as_json=as_json, text_renderer=render_text)

    @appstore_group.command(name="state")
    @click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
    def appstore_state(as_json: bool) -> None:
        """Inspect the current App Store dataset synchronization state."""
        def action() -> dict[str, Any]:
            from src.services.appstore_sync_manager import AppStoreSyncManager

            manager = AppStoreSyncManager()
            state = manager.get_state()
            runtime_status = manager.get_sync_status()
            return {
                **state,
                "running": runtime_status.get("status") == "running",
                "runtimeStatus": runtime_status.get("status"),
            }

        def render_text(payload: dict[str, Any]) -> str:
            return (
                f"App Store state: status={payload.get('syncStatus')} "
                f"running={payload.get('running')} "
                f"channel={payload.get('channel') or '-'} "
                f"dataset={payload.get('datasetVersion') or '-'} "
                f"lastSyncedAt={payload.get('lastSyncedAt') or '-'}"
            )

        run_cli_action(action, as_json=as_json, text_renderer=render_text)
