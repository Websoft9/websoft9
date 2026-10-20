from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from src.cli.cli_output import CLIError, MAX_TEXT_BUDGET_BYTES, mask_sensitive_text, run_cli_action, truncate_utf8_text


@click.group(name="git")
def git_group():
    """Inspect and update application configuration repositories in Gitea.

    This is not a general-purpose Git client. Repository changes do not redeploy
    applications unless explicitly requested.
    """


def _parse_key_value_pairs(pairs: tuple[str, ...]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            raise CLIError("INVALID_ARGUMENT", f"Invalid --set value '{item}': expected KEY=VALUE", exit_code=2)
        key, _, value = item.partition("=")
        key = key.strip()
        if not key:
            raise CLIError("INVALID_ARGUMENT", f"Invalid --set value '{item}': key cannot be empty", exit_code=2)
        if value == "******":
            raise CLIError("INVALID_ARGUMENT", f"Refusing to write masked placeholder '******' for key '{key}'", exit_code=2)
        updates[key] = value
    if not updates:
        raise CLIError("INVALID_ARGUMENT", "At least one --set KEY=VALUE option is required", exit_code=2)
    return updates


@git_group.command(name="repos")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_repos_command(as_json: bool) -> None:
    """List application configuration repositories in Gitea."""
    def action() -> dict[str, Any]:
        from src.services.gitea_manager import GiteaManager

        repos = GiteaManager().list_repos()
        return {
            "items": repos,
            "total": len(repos),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No configuration repositories found."
        lines = [f"Repositories ({len(items)}):"]
        for item in items:
            lines.append(f"- {item.get('name')} (branch={item.get('default_branch')}, empty={item.get('empty')})")
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="files")
@click.argument("app_id")
@click.option("--dir", "dir_path", default="", help="Optional subdirectory path inside the repository.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_repo_files_command(app_id: str, dir_path: str, as_json: bool) -> None:
    """List files and directories in an application's configuration repository."""
    def action() -> dict[str, Any]:
        from src.services.gitea_manager import GiteaManager

        listing = GiteaManager().list_repo_files(app_id, dir_path)
        return {
            "app_id": app_id,
            "head_sha": listing.get("head_sha") or "",
            "current_dir": listing.get("current_dir") or "",
            "files": listing.get("files") or [],
        }

    def render_text(payload: dict[str, Any]) -> str:
        files = payload.get("files") or []
        if not files:
            return f"No files in repository '{payload.get('app_id')}'."
        lines = [f"Repository {payload.get('app_id')} (head={payload.get('head_sha') or '-'}):"]
        for item in files:
            lines.append(f"- [{item.get('type')}] {item.get('path')} (size={item.get('size')} sha={item.get('sha') or '-'})")
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="cat")
@click.argument("app_id")
@click.argument("file_path")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def cat_repo_file_command(app_id: str, file_path: str, as_json: bool) -> None:
    """Read a text file from an application's configuration repository (secrets masked)."""
    def action() -> tuple[dict[str, Any], bool]:
        from src.services.gitea_manager import GiteaManager

        file_data = GiteaManager().read_repo_text_file(app_id, file_path)
        masked = mask_sensitive_text(file_data.get("content") or "")
        clipped, truncated = truncate_utf8_text(masked, MAX_TEXT_BUDGET_BYTES, keep_tail=False)
        return (
            {
                "app_id": app_id,
                "path": file_data.get("path"),
                "name": file_data.get("name"),
                "sha": file_data.get("sha"),
                "content": clipped,
            },
            truncated,
        )

    def render_text(payload: dict[str, Any]) -> str:
        return str(payload.get("content") or "")

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="env-set")
@click.argument("app_id")
@click.option("--set", "set_values", multiple=True, required=True, metavar="KEY=VALUE", help="Environment key/value to update (repeatable).")
@click.option("--sha", "expected_sha", help="Expected .env blob SHA for optimistic concurrency protection.")
@click.option("--yes", "-y", is_flag=True, help="Confirm updating repository .env file.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def env_set_command(app_id: str, set_values: tuple[str, ...], expected_sha: str | None, yes: bool, as_json: bool) -> None:
    """Update specific environment variables in an application's .env file."""
    def action() -> dict[str, Any]:
        from src.services.gitea_manager import GiteaManager

        updates = _parse_key_value_pairs(set_values)
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Updating .env in repository '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "keys": sorted(updates.keys())},
                )
            if not click.confirm(f"Update {len(updates)} variable(s) ({', '.join(sorted(updates.keys()))}) in '{app_id}/.env'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        result = GiteaManager().update_env_variables(app_id, updates, expected_sha=expected_sha)
        return {
            "app_id": app_id,
            **result,
        }

    def render_text(payload: dict[str, Any]) -> str:
        keys = ", ".join(payload.get("updated_keys") or [])
        return f"Updated .env in '{payload.get('app_id')}' (keys={keys}, sha={payload.get('sha')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="write")
@click.argument("app_id")
@click.argument("file_path")
@click.option("--from-file", "source_file", required=True, type=click.Path(exists=True, dir_okay=False, readable=True), help="Local file whose content will be written.")
@click.option("--sha", "expected_sha", required=True, help="Current blob SHA of the target file in Gitea (required for conflict check).")
@click.option("--yes", "-y", is_flag=True, help="Confirm writing the repository file.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def write_repo_file_command(app_id: str, file_path: str, source_file: str, expected_sha: str, yes: bool, as_json: bool) -> None:
    """Write a text file in an application's configuration repository with SHA conflict check."""
    def action() -> dict[str, Any]:
        from src.core.exception import CustomException
        from src.services.gitea_manager import GiteaManager

        content = Path(source_file).read_text(encoding="utf-8")
        if "******" in content:
            raise CLIError(
                "INVALID_ARGUMENT",
                "Refusing to write content containing masked secret placeholder '******'",
                details={"path": file_path},
                exit_code=2,
            )

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Writing '{file_path}' in repository '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "path": file_path},
                )
            if not click.confirm(f"Overwrite '{file_path}' in repository '{app_id}' (expected sha={expected_sha})?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        manager = GiteaManager()
        current = manager.get_file_content_from_repo(app_id, file_path)
        if not current:
            raise CustomException(404, "Not Found", f"File {file_path} not found in repository {app_id}")
        if str(current.get("sha") or "") != expected_sha.strip():
            raise CustomException(
                409,
                "Repository File Conflict",
                f"File {file_path} has been modified in Gitea (current sha={current.get('sha')}, expected={expected_sha.strip()}).",
            )

        result = manager.write_repo_text_file(app_id, file_path, content, sha=expected_sha.strip())
        return {
            "app_id": app_id,
            **result,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Updated '{payload.get('path')}' in '{payload.get('app_id')}' (new sha={payload.get('sha')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="rm")
@click.argument("app_id")
@click.argument("file_path")
@click.option("--sha", "expected_sha", required=True, help="Current blob SHA of the file to delete.")
@click.option("--yes", "-y", is_flag=True, help="Confirm deleting the repository file.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def rm_repo_file_command(app_id: str, file_path: str, expected_sha: str, yes: bool, as_json: bool) -> None:
    """Delete a non-core file from an application's configuration repository."""
    def action() -> dict[str, Any]:
        from src.services.gitea_manager import GiteaManager

        protected = {"docker-compose.yml", "docker-compose.yaml", ".env", "variables.json"}
        normalized = file_path.strip().strip("/")
        if normalized in protected:
            raise CLIError(
                "INVALID_REQUEST",
                f"Refusing to delete protected core file '{normalized}'",
                details={"app_id": app_id, "path": normalized},
            )
        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Deleting '{file_path}' from repository '{app_id}' requires --yes confirmation",
                    details={"app_id": app_id, "path": file_path},
                )
            if not click.confirm(f"Delete file '{file_path}' from repository '{app_id}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        result = GiteaManager().delete_repo_file(app_id, file_path, sha=expected_sha.strip())
        return {
            "app_id": app_id,
            **result,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Deleted '{payload.get('path')}' from '{payload.get('app_id')}' (head_sha={payload.get('head_sha')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="log")
@click.argument("app_id")
@click.option("--limit", type=click.IntRange(min=1, max=100), default=20, show_default=True, help="Maximum commits to return.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def git_log_command(app_id: str, limit: int, as_json: bool) -> None:
    """List commit history for an application's configuration repository."""
    def action() -> dict[str, Any]:
        from src.services.gitea_manager import GiteaManager

        commits = GiteaManager().list_repo_commits(app_id, limit=limit)
        return {
            "app_id": app_id,
            "items": commits,
            "total": len(commits),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return f"No commits found for '{payload.get('app_id')}'."
        return "\n".join(
            f"- {item.get('short_sha')} {item.get('date') or '-'} ({item.get('author') or '-'}): {item.get('message')}"
            for item in items
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="diff")
@click.argument("app_id")
@click.option("--commit", "target_ref", default=None, help="Commit SHA to inspect diff for (defaults to latest commit).")
@click.option("--base", "base_ref", default=None, help="Optional base commit/ref to compare against.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def git_diff_command(app_id: str, target_ref: str | None, base_ref: str | None, as_json: bool) -> None:
    """Show masked diff for a configuration repository commit or ref range."""
    def action() -> tuple[dict[str, Any], bool]:
        from src.services.gitea_manager import GiteaManager

        raw_diff = GiteaManager().get_repo_diff(app_id, target_ref=target_ref, base_ref=base_ref)
        masked_diff = mask_sensitive_text(str(raw_diff.get("diff") or ""))
        clipped_diff, truncated = truncate_utf8_text(masked_diff, MAX_TEXT_BUDGET_BYTES, keep_tail=False)
        return (
            {
                "app_id": app_id,
                "base": raw_diff.get("base"),
                "target": raw_diff.get("target"),
                "diff": clipped_diff,
            },
            truncated,
        )

    def render_text(payload: dict[str, Any]) -> str:
        return str(payload.get("diff") or "")

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@git_group.command(name="rollback")
@click.argument("app_id")
@click.option("--to", "target_commit", required=True, help="Target commit SHA to rollback configuration to.")
@click.option("--redeploy/--no-redeploy", default=False, show_default=True, help="Whether to redeploy the application stack after rolling back.")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), default=None, help="Endpoint ID when redeploying.")
@click.option("--yes", "-y", is_flag=True, help="Confirm rolling back configuration repository.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def git_rollback_command(app_id: str, target_commit: str, redeploy: bool, endpoint_id: int | None, yes: bool, as_json: bool) -> None:
    """Rollback an application's configuration repository to a previous commit (creates a new commit)."""
    def action() -> dict[str, Any]:
        import asyncio
        from src.services.app_manager import AppManger
        from src.services.compose_app_manager import ComposeAppManager
        from src.services.gitea_manager import GiteaManager

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Rolling back '{app_id}' configuration to '{target_commit}' (redeploy={redeploy}) requires --yes confirmation",
                    details={"app_id": app_id, "target_commit": target_commit, "redeploy": redeploy},
                )
            if not click.confirm(f"Rollback configuration of '{app_id}' to commit '{target_commit}' (redeploy={redeploy})?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        rollback_res = GiteaManager().rollback_repo_to_commit(app_id, target_commit)
        redeployed = False
        if redeploy and rollback_res.get("changed"):
            app_mgr = AppManger()
            app = app_mgr.get_app_by_id(
                app_id,
                endpoint_id,
                reconcile_stale=False,
                readonly_install_state=True,
                strict_exists=True,
            )
            if getattr(app, "is_compose_app", False):
                ComposeAppManager().redeploy_compose_app(app_id, endpoint_id, pull_image=False)
            else:
                asyncio.run(app_mgr.redeploy_app(app_id, False, endpoint_id))
            redeployed = True

        return {
            **rollback_res,
            "redeployed": redeployed,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"Rollback '{payload.get('app_id')}' -> {payload.get('target_commit')[:10]} "
            f"(changed={payload.get('changed')}, new_head={payload.get('new_head_sha')}, redeployed={payload.get('redeployed')})."
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)
