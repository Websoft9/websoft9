import base64

from src.core.apiHelper import APIHelper
from src.core.config import ConfigManager
from src.core.logger import logger


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
        self.owner = ConfigManager().get_value("gitea", "user_name")
        self.api = APIHelper(
            ConfigManager().get_value("gitea", "base_url"),
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