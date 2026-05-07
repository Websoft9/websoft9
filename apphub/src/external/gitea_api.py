import base64
import os
import socket
from urllib.parse import urlparse

from src.core.apiHelper import APIHelper
from src.core.config import ConfigManager
from src.core.logger import logger
from src.services.integration_credentials import IntegrationCredentialProvider


def resolve_gitea_api_base_url() -> str:
    fallback = os.getenv("WEBSOFT9_GITEA_API_BASE_URL", "http://127.0.0.1:3001/api/v1").rstrip("/")

    try:
        configured = (ConfigManager().get_value("gitea", "base_url") or "").rstrip("/")
    except Exception:
        return fallback

    if not configured:
        return fallback

    parsed = urlparse(configured)
    host = parsed.hostname
    if not parsed.scheme or not parsed.netloc or not host:
        return fallback

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        logger.error(f"Gitea base_url host '{host}' is unreachable; falling back to {fallback}")
        return fallback

    return configured


class GiteaAPI:
    """
    This class is used to interact with Gitea API

    Attributes:
        api (APIHelper): API helper

    Methods:
        get_repos() -> Response: Get repositories
        create_repo(repo_name: str) -> Response: Create repository
        remove_repo(repo_name: str) -> Response: Remove repository
        update_file_in_repo(repo_name: str, file_path: str, content: str) -> Response: Update file in repository
        get_file_content_from_repo(repo_name: str, file_path: str) -> Response: Get file content from repository
        update_file_content_in_repo(repo_name: str, file_path: str, content: str, sha: str) -> Response: Update file content in repository
    """

    def __init__(self):
        """
        Initialize the GiteaAPI instance
        """
        self.owner = IntegrationCredentialProvider().get_gitea_credentials().username
        self.api = APIHelper(
            resolve_gitea_api_base_url(),
            {
                "Content-Type": "application/json",
            },
        )

    def set_credential(self, credential: str):
        """
        Set credential

        Args:
            credential (str): Credential
        """
        self.api.headers["Authorization"] = f"Basic {credential}"

    # def get_repos(self):
    #     return self.api.get(path="user/repos", params={"page": 1, "limit": 1000})
    
    def get_repo_by_name(self, repo_name: str):
        """
        Get repository by name

        Args:
            repo_name (str): Repository name

        Returns:
            Response: Response from Gitea API
        """
        return self.api.get(path=f"repos/{self.owner}/{repo_name}")

    def create_repo(self, repo_name: str):
        """
        Create repository

        Args:
            repo_name (str): Repository name

        Returns:
            Response: Response from Gitea API
        """
        return self.api.post(
            path="user/repos",
            json={
                "default_branch": "main",
                "name": repo_name,
                "trust_model": "default",
                "private": True,
            },
        )

    def remove_repo(self, repo_name: str):
        """
        Remove repository

        Args:
            repo_name (str): Repository name

        Returns:
            Response: Response from Gitea API
        """
        return self.api.delete(path=f"repos/{self.owner}/{repo_name}")

    def get_file_content_from_repo(self, repo_name: str, file_path: str):
        """
        Get file content from repository

        Args:
            repo_name (str): Repository name
            file_path (str): File path

        Returns:
            Response: Response from Gitea API
        """
        return self.api.get(
            path=f"repos/{self.owner}/{repo_name}/contents/{file_path}",
            params={"ref": "main"}
        )
    
    def get_file_raw_from_repo(self, repo_name: str, file_path: str):
        """
        Get file raw from repository

        Args:
            repo_name (str): Repository name
            file_path (str): File path

        Returns:
            Response: Response from Gitea API
        """
        return self.api.get(
            path=f"repos/{self.owner}/{repo_name}/raw/{file_path}"
        )

    def update_file_content_in_repo(self, repo_name: str, file_path: str, content: str, sha: str):
        """
        Update file content in repository

        Args:
            repo_name (str): Repository name
            file_path (str): File path
            content (str): Content: base64 encoded
            sha (str): SHA

        Returns:
            Response: Response from Gitea API
        """
        return self.api.put(
            path=f"repos/{self.owner}/{repo_name}/contents/{file_path}",
            json={
                "branch": "main",
                "sha": sha,
                "content": content,
                "message": f"Update {file_path}",
            },
        )