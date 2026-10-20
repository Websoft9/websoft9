import base64
import os
import posixpath
import re
import tempfile
import time
from contextlib import contextmanager
from io import StringIO

from dotenv.parser import parse_stream
from git import Repo
from src.core.logger import logger
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.external.gitea_api import GiteaAPI
from src.services.integration_credentials import IntegrationCredentialProvider
from src.utils.env_file import format_env_assignment
from urllib.parse import urlparse, urlunparse


class GiteaManager:
    """
    Gitea Manager

    Methods:
        check_repo_exists: Check repo is exist.
        create_repo: Create repository.
        get_file_content_from_repo: Get file content from repository.
        update_file_in_repo: Update file in repository.
        remove_repo: Remove repository.
    """
    def __init__(self):
        """
        Init GiteaManager
        """
        try:
            self.gitea = GiteaAPI()
            self._set_basic_auth_credential()
        except Exception as e:
            logger.error(f"Init Gitea API Error:{e}")
            raise CustomException()
        
    def _set_basic_auth_credential(self):
        """
        Set basic auth credential
        """
        credentials = IntegrationCredentialProvider().get_gitea_credentials()
        username = credentials.username
        password = credentials.password
          
        credentials = f"{username}:{password}"
        credentials_encoded = base64.b64encode(credentials.encode()).decode()
        self.gitea.set_credential(credentials_encoded)

    def _normalize_clone_url(self, clone_url: str) -> str:
        try:
            parsed = urlparse(clone_url)
        except Exception:
            return clone_url

        if not parsed.scheme or not parsed.netloc:
            return clone_url

        if not parsed.path.startswith("/w9git/"):
            return clone_url

        runtime_layout = (os.getenv("WEBSOFT9_RUNTIME_LAYOUT") or "").strip().lower()
        public_origin = (os.getenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN") or "").strip()
        public_netloc = urlparse(public_origin).netloc if public_origin else ""

        # In the single-container product runtime, internal git push/clone must
        # bypass the platform-gateway and talk directly to Gitea on port 3001,
        # because the gateway enforces session-auth on /w9git/ while git HTTP
        # operations rely on Basic auth carried in the URL.
        # NOTE: use parsed.hostname (no port) for comparison because clone URLs
        # from Gitea include the port in netloc (e.g. 127.0.0.1:9000).
        if runtime_layout == "single-container-target" and parsed.hostname in {public_netloc, "127.0.0.1", "localhost"}:
            internal_path = parsed.path
            if internal_path.startswith("/w9git/"):
                internal_path = internal_path[len("/w9git"):]  # strip prefix so Gitea serves /owner/repo.git
            return urlunparse(parsed._replace(scheme="http", netloc="127.0.0.1:3001", path=internal_path))

        if parsed.hostname == "localhost":
            return urlunparse(parsed._replace(netloc="websoft9-git:3000"))

        return clone_url

    def check_repo_exists(self,repo_name: str):
        """
        Check repo is exist

        Args:
            repo_name (str): Repository name

        Returns:
            bool: True if repo is exist, False if repo is not exist, raise exception if error
        """
        response = self.gitea.get_repo_by_name(repo_name)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            logger.error(f"Check repo:{repo_name} exists error:{response.status_code}:{response.text}")
            raise CustomException()
        
    def create_repo(self, repo_name: str):
        """
        Create repository

        Args:
            repo_name (str): Repository name

        Returns:
            str: Repository clone url
        """
        response = self.gitea.create_repo(repo_name)
        if response.status_code == 201:
            repo_json = response.json()
            url = self._normalize_clone_url(repo_json["clone_url"])
            return url
        else:
            logger.error(f"Create repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException()

    def list_repos(self) -> list[dict]:
        response = self.gitea.get_repos()
        if response.status_code != 200:
            logger.error(f"List repos error:{response.status_code}:{response.text}")
            raise CustomException()
        repos = response.json()
        if not isinstance(repos, list):
            return []
        result: list[dict] = []
        for item in repos:
            if not isinstance(item, dict):
                continue
            result.append(
                {
                    "name": item.get("name"),
                    "full_name": item.get("full_name"),
                    "default_branch": item.get("default_branch") or "main",
                    "empty": bool(item.get("empty", False)),
                    "updated_at": item.get("updated_at"),
                }
            )
        result.sort(key=lambda entry: str(entry.get("name") or ""))
        return result
        
    @staticmethod
    def _validate_repo_file_path(file_path: str) -> str:
        raw = (file_path or "").strip().replace("\\", "/")
        if not raw or raw.startswith("/") or "\x00" in raw:
            raise CustomException(400, "Invalid Request", "Invalid repository file path")
        normalized = posixpath.normpath(raw)
        if normalized in {".", ".."} or normalized.startswith("../") or "/../" in f"/{normalized}/":
            raise CustomException(400, "Invalid Request", "Invalid repository file path")
        if normalized == ".git" or normalized.startswith(".git/") or normalized.startswith("src/.websoft9/"):
            raise CustomException(403, "Forbidden", "Access to internal repository metadata is not allowed")
        return normalized

    @staticmethod
    def _repo_file_sort_key(file_path: str) -> tuple[int, str]:
        priority_map = {
            "docker-compose.yml": 0,
            "docker-compose.yaml": 1,
            ".env": 2,
            "variables.json": 4,
            "Dockerfile": 5,
            "README.md": 8,
            "CHANGELOG.md": 9,
        }
        if file_path in priority_map:
            return (priority_map[file_path], file_path)
        if file_path.startswith(".env."):
            return (3, file_path)
        if file_path.startswith("src/"):
            return (6, file_path)
        return (7, file_path.lower())

    def list_repo_files(self, repo_name: str, dir_path: str = "") -> dict:
        normalized_dir = ""
        if dir_path and dir_path.strip().strip("/"):
            normalized_dir = self._validate_repo_file_path(dir_path.strip().strip("/"))

        head_sha = ""
        files: list[dict] = []
        all_entries: list[dict] = []

        if hasattr(self.gitea, "get_repo_directory_contents"):
            dir_resp = self.gitea.get_repo_directory_contents(repo_name, normalized_dir, ref="main")
            if dir_resp.status_code == 404:
                raise CustomException(404, "Not Found", f"Repository path {normalized_dir or repo_name} not found")
            if dir_resp.status_code != 200:
                logger.error(f"List repo:{repo_name} contents error:{dir_resp.status_code}:{dir_resp.text}")
                raise CustomException()

            entries = dir_resp.json()
            if isinstance(entries, dict):
                entries = [entries]
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    path = str(entry.get("path") or "").strip()
                    if not path or path == ".git" or path.startswith(".git/") or path.startswith("src/.websoft9/"):
                        continue
                    raw_type = str(entry.get("type") or "file")
                    item_type = "dir" if raw_type in {"dir", "tree"} else "file"
                    files.append(
                        {
                            "path": path,
                            "name": str(entry.get("name") or posixpath.basename(path)),
                            "type": item_type,
                            "size": int(entry.get("size") or 0) if item_type == "file" else 0,
                            "sha": str(entry.get("sha") or ""),
                            "last_commit_sha": str(entry.get("last_commit_sha") or ""),
                            "last_modified": str(entry.get("last_committer_date") or entry.get("last_author_date") or ""),
                        }
                    )

        if hasattr(self.gitea, "get_repo_tree"):
            tree_resp = self.gitea.get_repo_tree(repo_name, ref="main", recursive=True)
            if tree_resp.status_code == 404 and not files:
                raise CustomException(404, "Not Found", f"Repository {repo_name} not found")
            if tree_resp.status_code == 200:
                payload = tree_resp.json() or {}
                head_sha = str(payload.get("sha") or "")
                tree = payload.get("tree") if isinstance(payload.get("tree"), list) else []
                for entry in tree:
                    if not isinstance(entry, dict):
                        continue
                    raw_path = str(entry.get("path") or "").strip()
                    if not raw_path or raw_path == ".git" or raw_path.startswith(".git/") or raw_path.startswith("src/.websoft9/"):
                        continue
                    raw_type = str(entry.get("type") or "")
                    if raw_type not in {"tree", "blob"}:
                        continue
                    all_entries.append(
                        {
                            "path": raw_path,
                            "name": posixpath.basename(raw_path),
                            "type": "dir" if raw_type == "tree" else "file",
                            "size": int(entry.get("size") or 0) if raw_type == "blob" else 0,
                            "sha": str(entry.get("sha") or ""),
                        }
                    )
                if not files:
                    seen_dirs: set[str] = set()
                    prefix = f"{normalized_dir}/" if normalized_dir else ""
                    for entry in all_entries:
                        raw_path = entry["path"]
                        if prefix:
                            if not raw_path.startswith(prefix):
                                continue
                            rel = raw_path[len(prefix):]
                        else:
                            rel = raw_path
                        if not rel:
                            continue
                        if "/" in rel:
                            child_dir = rel.split("/", 1)[0]
                            dir_full_path = f"{prefix}{child_dir}"
                            if dir_full_path not in seen_dirs:
                                seen_dirs.add(dir_full_path)
                                files.append(
                                    {
                                        "path": dir_full_path,
                                        "name": child_dir,
                                        "type": "dir",
                                        "size": 0,
                                        "sha": "",
                                        "last_commit_sha": "",
                                        "last_modified": "",
                                    }
                                )
                        elif entry["type"] == "file":
                            files.append(
                                {
                                    "path": raw_path,
                                    "name": entry["name"],
                                    "type": "file",
                                    "size": entry["size"],
                                    "sha": entry["sha"],
                                    "last_commit_sha": "",
                                    "last_modified": "",
                                }
                            )

        files.sort(key=lambda item: (0 if item.get("type") == "dir" else 1, item["name"].lower()))
        return {"head_sha": head_sha, "current_dir": normalized_dir, "files": files, "all_entries": all_entries or files}

    def read_repo_text_file(self, repo_name: str, file_path: str) -> dict:
        normalized_path = self._validate_repo_file_path(file_path)
        file_info = self.get_file_content_from_repo(repo_name, normalized_path)
        if not file_info:
            raise CustomException(404, "Not Found", f"File {normalized_path} not found")
        raw_content = file_info.get("content") or ""
        try:
            decoded_bytes = base64.b64decode(raw_content)
        except Exception as exc:
            raise CustomException(400, "Invalid Request", f"Failed to decode file {normalized_path}") from exc
        if len(decoded_bytes) > 2 * 1024 * 1024:
            raise CustomException(400, "File Too Large", "Only files up to 2 MB can be edited in the console")
        try:
            text_content = decoded_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CustomException(400, "Unsupported File", "Only UTF-8 text files can be viewed or edited") from exc
        return {
            "path": normalized_path,
            "name": file_info.get("name") or posixpath.basename(normalized_path),
            "sha": file_info.get("sha") or "",
            "content": text_content,
        }

    def write_repo_text_file(self, repo_name: str, file_path: str, content: str, sha: str | None = None) -> dict:
        normalized_path = self._validate_repo_file_path(file_path)
        resolved_sha = (sha or "").strip()
        if not resolved_sha:
            existing = self.get_file_content_from_repo(repo_name, normalized_path)
            if not existing or not existing.get("sha"):
                raise CustomException(404, "Not Found", f"File {normalized_path} not found")
            resolved_sha = str(existing["sha"])

        encoded_content = base64.b64encode((content or "").encode("utf-8")).decode("utf-8")
        response = self.gitea.update_file_content_in_repo(repo_name, normalized_path, encoded_content, resolved_sha)
        if response.status_code == 422 and "sha does not match" in (response.text or ""):
            raise CustomException(
                409,
                "Repository File Conflict",
                f"File {normalized_path} has been modified in Gitea by another session. Reload the latest version before saving.",
            )
        if response.status_code != 200:
            logger.error(f"Update file:{normalized_path} content in repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException(400, "Update Failed", f"Failed to update {normalized_path} in repository")
        result = response.json() if response.text else {}
        content_meta = result.get("content") if isinstance(result, dict) and isinstance(result.get("content"), dict) else {}
        commit_meta = result.get("commit") if isinstance(result, dict) and isinstance(result.get("commit"), dict) else {}
        return {
            "path": normalized_path,
            "sha": str(content_meta.get("sha") or ""),
            "head_sha": str(commit_meta.get("sha") or ""),
        }

    def update_env_variables(
        self,
        repo_name: str,
        updates: dict[str, str],
        *,
        expected_sha: str | None = None,
    ) -> dict:
        if not updates:
            raise CustomException(400, "Invalid Request", "At least one environment key=value update is required")
        normalized_updates = {}
        for key, value in updates.items():
            key = str(key or "").strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise CustomException(400, "Invalid Request", "Invalid environment variable key")
            if str(value) == "******":
                raise CustomException(400, "Invalid Request", f"Refusing to overwrite '{key}' with masked placeholder '******'")
            normalized_updates[key] = str(value)

        file_data = self.read_repo_text_file(repo_name, ".env")
        current_sha = str(file_data.get("sha") or "")
        if expected_sha and expected_sha.strip() and expected_sha.strip() != current_sha:
            raise CustomException(
                409,
                "Repository File Conflict",
                "File .env has been modified in Gitea by another session. Reload the latest version before saving.",
            )

        updated_keys: list[str] = []
        chunks: list[str] = []

        def assignment(key: str) -> str:
            return format_env_assignment(key, normalized_updates[key])

        for binding in parse_stream(StringIO(file_data.get("content") or "")):
            if not binding.error and binding.key in normalized_updates:
                prefix = re.match(r"\s*(?:export[^\S\r\n]+)?", binding.original.string).group(0)
                chunks.append(prefix + assignment(binding.key))
                if binding.key not in updated_keys:
                    updated_keys.append(binding.key)
            else:
                chunks.append(binding.original.string)

        new_content = "".join(chunks)
        for key in normalized_updates:
            if key not in updated_keys:
                if new_content and not new_content.endswith("\n"):
                    new_content += "\n"
                new_content += assignment(key)
                updated_keys.append(key)

        write_res = self.write_repo_text_file(repo_name, ".env", new_content, sha=current_sha)
        return {
            **write_res,
            "updated_keys": updated_keys,
        }

    def delete_repo_file(self, repo_name: str, file_path: str, sha: str | None = None) -> dict:
        normalized_path = self._validate_repo_file_path(file_path)
        protected_root_files = {"docker-compose.yml", "docker-compose.yaml", ".env", "variables.json"}
        if normalized_path in protected_root_files:
            raise CustomException(
                400,
                "Protected Repository File",
                f"Refusing to delete core configuration file '{normalized_path}'",
            )

        current = self.get_file_content_from_repo(repo_name, normalized_path)
        if not current or not current.get("sha"):
            raise CustomException(404, "Not Found", f"File {normalized_path} not found")
        current_sha = str(current["sha"])
        if sha and sha.strip() and sha.strip() != current_sha:
            raise CustomException(
                409,
                "Repository File Conflict",
                f"File {normalized_path} has been modified in Gitea (current sha={current_sha}, expected={sha.strip()}).",
            )
        response = self.gitea.delete_file_content_in_repo(repo_name, normalized_path, current_sha)
        if response.status_code not in {200, 204}:
            logger.error(f"Delete file:{normalized_path} in repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException(400, "Delete Failed", f"Failed to delete {normalized_path} from repository")
        result = response.json() if getattr(response, "text", "") else {}
        commit_meta = result.get("commit") if isinstance(result, dict) and isinstance(result.get("commit"), dict) else {}
        return {
            "path": normalized_path,
            "deleted_sha": current_sha,
            "head_sha": str(commit_meta.get("sha") or ""),
        }

    def list_repo_commits(self, repo_name: str, limit: int = 20) -> list[dict]:
        response = self.gitea.get_repo_commits(repo_name, sha="main", limit=limit)
        if response.status_code == 404:
            raise CustomException(404, "Not Found", f"Repository {repo_name} not found")
        if response.status_code != 200:
            logger.error(f"List commits for repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException()
        raw_commits = response.json()
        if not isinstance(raw_commits, list):
            return []
        commits: list[dict] = []
        for item in raw_commits[:limit]:
            if not isinstance(item, dict):
                continue
            commit_info = item.get("commit") or {}
            author_info = commit_info.get("author") or {}
            commits.append(
                {
                    "sha": item.get("sha"),
                    "short_sha": str(item.get("sha") or "")[:10],
                    "message": str(commit_info.get("message") or "").strip(),
                    "author": author_info.get("name") or author_info.get("email"),
                    "date": author_info.get("date") or item.get("created"),
                }
            )
        return commits

    def get_repo_diff(self, repo_name: str, target_ref: str | None = None, base_ref: str | None = None) -> dict:
        if base_ref:
            from git.exc import BadName, BadObject, GitCommandError

            # Gitea's comparison API returns metadata, not a unified tree diff.
            with self._clone_repo(repo_name) as (repo, _credentials):
                try:
                    base = repo.commit(base_ref).hexsha
                    target = repo.commit(target_ref or "origin/main").hexsha
                except (BadName, BadObject, ValueError, GitCommandError) as exc:
                    raise CustomException(404, "Not Found", f"Comparison refs not found in {repo_name}") from exc
                return {
                    "repo": repo_name,
                    "base": base_ref,
                    "target": target_ref or target,
                    "diff": repo.git.diff("--no-ext-diff", "--no-textconv", base, target, "--"),
                }

        resolved_commit = (target_ref or "").strip()
        if not resolved_commit:
            commits = self.list_repo_commits(repo_name, limit=1)
            if not commits:
                raise CustomException(404, "Not Found", f"No commits found in repository {repo_name}")
            resolved_commit = str(commits[0].get("sha") or "")

        diff_resp = self.gitea.get_commit_diff(repo_name, resolved_commit)
        if diff_resp.status_code == 404:
            raise CustomException(404, "Not Found", f"Commit '{resolved_commit}' not found in repository {repo_name}")
        if diff_resp.status_code != 200:
            logger.error(f"Get commit diff for repo:{repo_name} commit:{resolved_commit} error:{diff_resp.status_code}:{diff_resp.text}")
            raise CustomException()
        return {
            "repo": repo_name,
            "base": base_ref,
            "target": resolved_commit,
            "diff": str(diff_resp.text or ""),
        }

    @contextmanager
    def _clone_repo(self, repo_name: str):
        repo_resp = self.gitea.get_repo_by_name(repo_name)
        if repo_resp.status_code == 404:
            raise CustomException(404, "Not Found", f"Repository {repo_name} not found")
        if repo_resp.status_code != 200:
            raise CustomException()
        repo_json = repo_resp.json() or {}
        clone_url = self._normalize_clone_url(str(repo_json.get("clone_url") or ""))
        credentials = IntegrationCredentialProvider().get_gitea_credentials()

        from src.services.git_manager import GitManager

        with tempfile.TemporaryDirectory(prefix="repo-config-") as temp_root:
            clone_path = os.path.join(temp_root, "repo")
            git_mgr = GitManager(clone_path)
            git_mgr.clone_remote_repo_to_local(clone_url, credentials.username, credentials.password)
            with Repo(clone_path) as repo:
                yield repo, credentials

    def rollback_repo_to_commit(self, repo_name: str, target_commit: str) -> dict:
        from git import Actor, GitCommandError, PushInfo

        target = str(target_commit or "").strip()
        if not target or not all(ch.isalnum() or ch in "-_." for ch in target):
            raise CustomException(400, "Invalid Request", "Invalid target commit SHA")

        with self._clone_repo(repo_name) as (repo, credentials):
            try:
                resolved_target = repo.commit(target).hexsha
            except Exception as exc:
                raise CustomException(400, "Invalid Request", f"Target commit '{target}' not found in repository '{repo_name}'") from exc

            repo.git.checkout("--detach", "refs/remotes/origin/main")
            head_before = repo.head.commit.hexsha
            if resolved_target == head_before:
                return {
                    "app_id": repo_name,
                    "target_commit": resolved_target,
                    "new_head_sha": head_before,
                    "changed": False,
                }

            repo.git.read_tree("--reset", "-u", resolved_target)
            if repo.index.write_tree().hexsha == repo.head.commit.tree.hexsha:
                return {
                    "app_id": repo_name,
                    "target_commit": resolved_target,
                    "new_head_sha": head_before,
                    "changed": False,
                }
            actor = Actor(credentials.username, credentials.email)
            repo.index.commit(f"Rollback configuration to {resolved_target[:10]}", author=actor, committer=actor)
            origin = repo.remote(name="origin")
            try:
                pushed = origin.push("HEAD:refs/heads/main")
                pushed.raise_if_error()
            except GitCommandError as exc:
                raise CustomException(502, "Rollback Push Failed", "Failed to push configuration rollback") from exc
            error_flags = PushInfo.ERROR | PushInfo.REJECTED | PushInfo.REMOTE_REJECTED | PushInfo.REMOTE_FAILURE
            if not pushed or any(info.flags & error_flags for info in pushed):
                raise CustomException(502, "Rollback Push Failed", "Gitea rejected the configuration rollback")
            new_head = repo.head.commit.hexsha
            return {
                "app_id": repo_name,
                "target_commit": resolved_target,
                "previous_head_sha": head_before,
                "new_head_sha": new_head,
                "changed": True,
            }

    def get_file_content_from_repo(self, repo_name: str, file_path: str):
        """
        Get file content from repository

        Args:
            repo_name (str): Repository name
            file_path (str): File path

        Returns:
            dict: File content
        """
        response = self.gitea.get_file_content_from_repo(repo_name, file_path)
        if response.status_code == 200:
            response_json = response.json() # The gitea Api: if the repo is empty, the response is: []
            if not response_json:
                return None
            else:
                return {
                    "name": response_json["name"],
                    "encoding": response_json["encoding"],
                    "sha": response_json["sha"],
                    "content": response_json["content"],
                }
        elif response.status_code == 404:
            return None
        else:
            logger.error(f"Get file:{file_path} content from repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException()

    def update_file_in_repo(self, repo_name: str, file_path: str, content: str,sha: str):
        """
        Update file in repository

        Args:
            repo_name (str): Repository name
            file_path (str): File path
            content (str): File content
            sha (str): File sha
        """
        response = self.gitea.update_file_content_in_repo(repo_name, file_path, content, sha)
        if response.status_code != 200:
            logger.error(f"Update file:{file_path} content in repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException()

    def create_file_in_repo(self, repo_name: str, file_path: str, content: str):
        """
        Create file in repository

        Args:
            repo_name (str): Repository name
            file_path (str): File path
            content (str): File content (base64 encoded)
        """
        response = self.gitea.create_file_content_in_repo(repo_name, file_path, content)
        if response.status_code != 201:
            logger.error(f"Create file:{file_path} content in repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException()
        
    def remove_repo(self, repo_name: str):
        """
        Remove repository

        Args:
            repo_name (str): Repository name
        """
        response = self.gitea.remove_repo(repo_name)
        if response.status_code != 204:
            logger.error(f"Remove repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException()
        
    def get_file_raw_from_repo(self, repo_name: str, file_path: str):
        """
        Get a file from a repository

        Args:
            repo_name (str): Repository name
            file_path (str): File path

        Returns:
            dict: File content
        """
        response = self.gitea.get_file_raw_from_repo(repo_name, file_path)
        if response.status_code == 200:
            return response.text
        elif response.status_code == 404:
            return None
        else:
            logger.error(f"Get file:{file_path} content from repo:{repo_name} error:{response.status_code}:{response.text}")
            raise CustomException()

    def wait_for_repo_files(self, repo_name: str, repo_url: str, user_name: str, user_pwd: str, file_paths: list[str], timeout_seconds: int = 20, poll_interval: int = 1):
        pending_paths = [path for path in file_paths if path]
        if not pending_paths:
            return

        deadline = time.time() + max(timeout_seconds, 1)
        while True:
            remaining = list(pending_paths)
            try:
                from src.services.git_manager import GitManager

                with tempfile.TemporaryDirectory(prefix=f"repo-ready-{repo_name}-") as temp_root:
                    clone_path = os.path.join(temp_root, "repo")
                    GitManager(clone_path).clone_remote_repo_to_local(repo_url, user_name, user_pwd)
                    remaining = [
                        path for path in pending_paths
                        if not os.path.isfile(os.path.join(clone_path, path))
                    ]
            except CustomException:
                remaining = list(pending_paths)

            if not remaining:
                return

            if time.time() >= deadline:
                logger.error(
                    f"Repository files not ready after push for repo:{repo_name}: {remaining}"
                )
                raise CustomException(
                    status_code=400,
                    message="Invalid Request",
                    details=(
                        "The application repository is not ready for deployment yet: "
                        + ", ".join(remaining[:5])
                    ),
                )

            time.sleep(max(poll_interval, 1))
