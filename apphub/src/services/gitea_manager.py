import base64
import os
from git import Repo
from src.core.logger import logger
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.external.gitea_api import GiteaAPI
from src.services.integration_credentials import IntegrationCredentialProvider
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

        # In the single-container product runtime, git push/clone must use the
        # internal platform-gateway listener instead of the external published port.
        if runtime_layout == "single-container-target" and parsed.netloc in {public_netloc, "127.0.0.1", "localhost"}:
            return urlunparse(parsed._replace(scheme="http", netloc="127.0.0.1:9000"))

        if parsed.netloc == "localhost":
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

