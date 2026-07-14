"""
ComposeAppManager — lifecycle management for custom Docker Compose applications.

Custom compose apps are identified by an internal metadata file stored in Gitea,
while the user-facing .env remains reserved for user-defined variables only.
They share the same Portainer/Gitea infrastructure as marketplace apps but require
a separate management surface because their update, edit, and redeploy flows differ.
"""
import json
import os
import shutil
import tempfile

from git import GitCommandError, Repo

from src.core.exception import CustomException
from src.core.logger import logger
from src.services.gitea_manager import GiteaManager
from src.services.integration_credentials import IntegrationCredentialProvider
from src.services.portainer_manager import PortainerManager
from src.utils.file_manager import FileHelper

_COMPOSE_DIST = "compose"
_COMPOSE_METADATA_PATH = ".websoft9/compose-metadata.json"


def _get_endpoint_id(portainer: PortainerManager, endpoint_id: int | None) -> int:
    return endpoint_id if endpoint_id is not None else portainer.get_local_endpoint_id()


def _read_compose_metadata(gitea: GiteaManager, app_id: str) -> dict:
    """Read internal compose metadata from the app's Gitea repository."""
    try:
        raw_content = gitea.get_file_raw_from_repo(app_id, _COMPOSE_METADATA_PATH)
        if not raw_content:
            return {}
        payload = json.loads(raw_content)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _is_compose_app(portainer: PortainerManager, app_id: str, endpoint_id: int) -> bool:
    """Determine if an app is a custom compose app by checking Portainer stack properties.
    
    Compose apps have a GitConfig (deployed via Gitea) but no W9_APP_NAME env var
    (unlike marketplace apps which set W9_APP_NAME in container env)."""
    try:
        stack = portainer.get_stack_by_name(app_id, endpoint_id)
        if not stack:
            return False
        git_config = stack.get("GitConfig") or {}
        if not git_config:
            return False
        containers = portainer.get_containers_by_stack_name(app_id, endpoint_id) or []
        # If no containers exist, this is not a compose app — it's either
        # a failed marketplace install or an empty stack.
        if not containers:
            return False
        for c in containers:
            env = c.get("Config", {}).get("Env") or []
            for e in env:
                if e.startswith("W9_APP_NAME="):
                    return False  # has marketplace env → not compose
        return True
    except Exception:
        return False


def _require_stack(portainer: PortainerManager, app_id: str, endpoint_id: int) -> dict:
    """Return Portainer stack dict or raise 404."""
    stack = portainer.get_stack_by_name(app_id, endpoint_id)
    if not stack:
        raise CustomException(404, "Not Found", f"Compose app '{app_id}' not found")
    return stack


def _require_compose_app(portainer: PortainerManager, app_id: str, endpoint_id: int):
    """Validate that the app is a custom compose app, return AppResponse."""
    if not _is_compose_app(portainer, app_id, endpoint_id):
        raise CustomException(
            400, "Invalid Request",
            f"'{app_id}' is not a custom compose application (dist={dist!r})"
        )
    from src.services.app_manager import AppManger
    return AppManger().get_app_by_id(app_id, endpoint_id)


def _parse_user_env(env_content: str) -> list[dict]:
    """Parse .env content into user-visible key-value pairs, excluding W9_* vars."""
    entries = []
    for line in env_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key.startswith("W9_"):
            continue
        entries.append({"key": key, "value": value})
    return entries


def _list_src_files(gitea: GiteaManager, app_id: str) -> list[dict]:
    """List config/mount files under src/ in the Gitea repo (stub — returns empty list)."""
    return []


class ComposeAppManager:
    """Manages the lifecycle of custom Docker Compose applications."""

    # ── List / Detail ──────────────────────────────────────────────────────────

    def list_compose_apps(self, endpoint_id: int | None = None, locale: str = "en") -> list:
        """Return AppResponse objects for all apps whose metadata marks them as compose apps."""
        from src.services.app_manager import AppManger
        portainer = PortainerManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        stacks = portainer.get_stacks(eid) or []
        compose_app_ids = [
            stack.get("Name")
            for stack in stacks
            if stack.get("Name") and _is_compose_app(portainer, stack["Name"], eid)
        ]
        result = []
        for app_id in compose_app_ids:
            try:
                result.append(AppManger().get_app_by_id(app_id, eid, locale))
            except Exception as exc:
                logger.warning(f"list_compose_apps: failed to load '{app_id}': {exc}")
        return result

    def get_compose_app(self, app_id: str, endpoint_id: int | None = None, locale: str = "en"):
        """Return detail for a single compose app (validated via internal metadata)."""
        portainer = PortainerManager()
        gitea = GiteaManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        return _require_compose_app(portainer, app_id, eid)

    # ── Content (Gitea) ────────────────────────────────────────────────────────

    def get_compose_content(self, app_id: str) -> dict:
        """
        Read docker-compose.yml and .env from the app's Gitea repository.

        Returns:
            {
                app_id: str,
                compose_content: str,        # raw YAML
                env: [{"key": ..., "value": ...}],   # user-defined vars only (no W9_*)
                mounts: [{"path": ..., "content": ...}]   # files under src/
            }
        """
        gitea = GiteaManager()
        compose_content = gitea.get_file_raw_from_repo(app_id, "docker-compose.yml")
        if compose_content is None:
            raise CustomException(404, "Not Found", f"docker-compose.yml not found in Gitea repo '{app_id}'")
        env_content = gitea.get_file_raw_from_repo(app_id, ".env") or ""
        return {
            "app_id": app_id,
            "compose_content": compose_content,
            "env": _parse_user_env(env_content),
            "mounts": _list_src_files(gitea, app_id),
        }

    # ── Start / Stop / Restart ─────────────────────────────────────────────────

    def start_compose_app(self, app_id: str, endpoint_id: int | None = None) -> None:
        portainer = PortainerManager()
        gitea = GiteaManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        _require_compose_app(portainer, app_id, eid)
        stack = _require_stack(portainer, app_id, eid)
        stack_id = stack.get("Id")
        if stack_id is None:
            raise CustomException(404, "Not Found", f"Portainer stack for '{app_id}' has no Id")
        portainer.up_stack(stack_id, eid)

    def stop_compose_app(self, app_id: str, endpoint_id: int | None = None) -> None:
        portainer = PortainerManager()
        gitea = GiteaManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        _require_compose_app(portainer, app_id, eid)
        portainer.stop_stack(app_id, eid)

    def restart_compose_app(self, app_id: str, endpoint_id: int | None = None) -> None:
        portainer = PortainerManager()
        gitea = GiteaManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        _require_compose_app(portainer, app_id, eid)
        stack = _require_stack(portainer, app_id, eid)
        stack_id = stack.get("Id")
        if stack_id is None:
            raise CustomException(404, "Not Found", f"Portainer stack for '{app_id}' has no Id")
        portainer.stop_stack(app_id, eid)
        portainer.up_stack(stack_id, eid)

    # ── Redeploy (same content, from Gitea) ────────────────────────────────────

    def redeploy_compose_app(
        self,
        app_id: str,
        endpoint_id: int | None = None,
        pull_image: bool = True,
    ) -> None:
        """Trigger Portainer to re-pull from Gitea without changing compose content."""
        portainer = PortainerManager()
        gitea = GiteaManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        _require_compose_app(portainer, app_id, eid)
        stack = _require_stack(portainer, app_id, eid)
        stack_id = stack.get("Id")
        if stack_id is None:
            raise CustomException(404, "Not Found", f"Portainer stack for '{app_id}' has no Id")
        stack_status = stack.get("Status", 0)
        # Inactive stacks (uninstalled but data retained) need up_stack rather
        # than the git-redeploy flow.  Portainer's git/redeploy endpoint is
        # designed for updating already-active stacks and may silently no-op
        # on inactive ones, leaving the status stuck at Inactive.
        if stack_status == 2:
            portainer.up_stack(stack_id, eid)
            return
        credentials = IntegrationCredentialProvider().get_gitea_credentials()
        portainer.redeploy_stack(stack_id, eid, pull_image, credentials.username, credentials.password)

    # ── Update (edit compose content → push Gitea → redeploy) ─────────────────

    def update_compose_content(
        self,
        app_id: str,
        compose_content: str,
        env: list[dict],
        mounts: list[dict],
        endpoint_id: int | None = None,
    ) -> None:
        """
        Update compose.yml / .env / mount files in the Gitea repo and redeploy.

        Args:
            app_id: The compose app ID (Portainer stack name / Gitea repo name).
            compose_content: New raw YAML for docker-compose.yml.
            env: List of {"key": ..., "value": ...} user env vars.
            mounts: List of {"path": ..., "content": ...} config file overrides.
            endpoint_id: Portainer endpoint (uses local if None).
        """
        portainer = PortainerManager()
        gitea = GiteaManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        _require_compose_app(portainer, app_id, eid)
        stack = _require_stack(portainer, app_id, eid)
        stack_id = stack.get("Id")
        if stack_id is None:
            raise CustomException(404, "Not Found", f"Portainer stack for '{app_id}' has no Id")

        # Resolve Gitea repo URL from Portainer stack GitConfig
        git_config = stack.get("GitConfig") or {}
        repo_url = git_config.get("URL")
        if not repo_url:
            raise CustomException(
                500, "Internal Server Error",
                f"Cannot determine Gitea repository URL for '{app_id}' from Portainer stack GitConfig"
            )

        credentials = IntegrationCredentialProvider().get_gitea_credentials()

        # --- Clone → modify → commit → push ---
        temp_root = tempfile.mkdtemp(prefix=f"compose-update-{app_id}-")
        workspace = os.path.join(temp_root, app_id)
        try:
            from src.services.git_manager import GitManager
            git_mgr = GitManager(workspace)
            git_mgr.clone_remote_repo_to_local(repo_url, credentials.username, credentials.password)

            # Write updated docker-compose.yml
            FileHelper.write_file(os.path.join(workspace, "docker-compose.yml"), compose_content)

            user_lines = [f"{e['key']}={e['value']}" for e in env]
            FileHelper.write_file(
                os.path.join(workspace, ".env"),
                "\n".join(user_lines) + "\n",
            )

            # Write mount / config files
            for mount in mounts:
                target_path = os.path.join(workspace, mount["path"].lstrip("/"))
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                FileHelper.write_file(target_path, mount["content"])

            # Commit and push
            repo = Repo(workspace)
            repo.git.add(".")
            try:
                repo.git.commit("-m", "Update compose content")
            except GitCommandError:
                pass  # Nothing changed — still redeploy below
            repo.git.push("origin", "main")

        except CustomException:
            raise
        except Exception as exc:
            logger.error(f"Failed to update compose content for {app_id}: {exc}")
            raise CustomException(500, "Internal Server Error", f"Failed to push updated compose content: {exc}")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        # Redeploy from updated Gitea repo
        portainer.redeploy_stack(stack_id, eid, True, credentials.username, credentials.password)

    # ── Remove ─────────────────────────────────────────────────────────────────

    def remove_compose_app(self, app_id: str, endpoint_id: int | None = None) -> None:
        """
        Fully remove a compose app:
        - Remove Portainer stack and all associated volumes
        - Delete the Gitea repository
        """
        portainer = PortainerManager()
        gitea = GiteaManager()
        eid = _get_endpoint_id(portainer, endpoint_id)
        _require_compose_app(portainer, app_id, eid)

        stack = portainer.get_stack_by_name(app_id, eid)
        if stack:
            stack_id = stack.get("Id")
            if stack_id is not None:
                try:
                    portainer.remove_stack_and_volumes(stack_id, eid)
                except Exception as exc:
                    logger.warning(f"Failed to remove Portainer stack for {app_id}: {exc}")
                    try:
                        portainer.remove_vloumes(app_id, eid)
                    except Exception:
                        pass

        if gitea.check_repo_exists(app_id):
            try:
                gitea.remove_repo(app_id)
            except Exception as exc:
                logger.warning(f"Failed to remove Gitea repo for {app_id}: {exc}")
