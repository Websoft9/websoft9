import os
from urllib.parse import urlparse, urlunparse

from git import Repo, GitCommandError

from src.core.exception import CustomException
from src.core.logger import logger
from src.services.integration_credentials import IntegrationCredentialProvider

class GitManager:
    """
    This class is used to interact with Git

    Attributes:
        local_path (str): The path to the local git repository.

    Methods:
        init_local_repo_from_dir() -> None: Initialize a local git repository from a directory.
        push_local_repo_to_remote_repo(remote_url:str,user_name:str,user_pwd:str) -> None: Push a local git repository to a remote origin.
    """

    def __init__(self,local_path:str):
        """
        Initialize the GitManager instance
        """
        self.local_path = local_path

    def _normalize_clone_url(self, remote_url: str) -> str:
        try:
            parsed = urlparse(remote_url)
        except Exception:
            return remote_url

        if not parsed.scheme or not parsed.netloc:
            return remote_url

        runtime_layout = (os.getenv("WEBSOFT9_RUNTIME_LAYOUT") or "").strip().lower()
        public_origin = (os.getenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN") or "").strip()
        public_host = urlparse(public_origin).hostname if public_origin else ""

        if runtime_layout == "single-container-target" and parsed.hostname in {"websoft9-git", "localhost", "127.0.0.1", public_host}:
            normalized_path = parsed.path
            if normalized_path.startswith("/w9git/"):
                normalized_path = normalized_path[len("/w9git"):]
            return urlunparse(parsed._replace(scheme="http", netloc="127.0.0.1:3001", path=normalized_path))

        return remote_url

    def init_local_repo_from_dir(self):
        """
            Initialize a local git repository from a directory.
        """
        # Validate the repo path.
        if not os.path.exists(self.local_path):
            logger.error(f"When initializing a local git repository, the path {self.local_path} does not exist.")
            raise CustomException()

        # Initialize the repository
        try:
            repo = Repo.init(self.local_path)
        except GitCommandError as e:
            logger.error(f"When initializing a local git repository,failed to initialize git repository at {self.local_path}: {str(e)}")
            raise CustomException()
        
        # Add all files to the index and commit.
        try:
            config_writer = repo.config_writer()
            credentials = IntegrationCredentialProvider().get_gitea_credentials()
            config_writer.set_value('user', 'name', credentials.username)
            config_writer.set_value('user', 'email', credentials.email)
            config_writer.release()
            repo.git.add('.')
            repo.git.commit('-m', 'Initial commit')
        except GitCommandError as e:
            logger.error(f"When initializing a local git repository,failed to add/commit files in git repository at {self.local_path}: {str(e)}")
            raise CustomException()
        
    def push_local_repo_to_remote_repo(self,remote_url:str,user_name:str,user_pwd:str):
        """
        Push a local git repository to a remote origin.

        Args:
            repo_path (str): The path to the local git repository.
            remote_url (str): The URL of the remote origin.
            user_name (str): The user name to use when authenticating with the remote origin.
            user_pwd (str): The password to use when authenticating with the remote origin.

        Raises:
            CustomException: If there is an error pushing the local git repository to the remote origin.
        """
        # Validate the repo path.
        if not os.path.exists(self.local_path):
            logger.error(f"Invalid repo path: {self.local_path}")
            raise CustomException()
        
        remote_url = self._normalize_clone_url(remote_url)

        try:
            # Parse the remote URL.
            parsed = urlparse(remote_url)

            # Get the network location.
            auth_netloc = f"{user_name}:{user_pwd}@{parsed.netloc}"

            # Create a new ParseResult with the updated network location
            auth_parsed = parsed._replace(netloc=auth_netloc)
            auth_repo_url = urlunparse(auth_parsed)
        except Exception as e:
            logger.error(f"Failed to parse remote URL {remote_url}: {str(e)}")
            raise CustomException()

        # Set remote origin URL.
        try: 
            repo = Repo(self.local_path)
            repo.create_remote('origin', url=auth_repo_url) 
        except (ValueError, GitCommandError) as e:
            logger.error(f"Failed to set remote origin URL in git repository at {self.local_path}: {str(e)}")
            raise CustomException()

        # Push local code to main branch on remote origin.
        try:
            repo.git.push('origin', 'HEAD:refs/heads/main')
        except GitCommandError as e:
            logger.error(f"Failed to push from 'main' branch in git repository at {self.local_path} to remote '{remote_url}': {str(e)}")
            raise CustomException()  
        
    def clone_remote_repo_to_local(self,remote_url:str,user_name:str,user_pwd:str):
        """
        Clone a remote git repository to a local path.

        Args:
            remote_url (str): The URL of the remote origin.
            user_name (str): The user name to use when authenticating with the remote origin.
            user_pwd (str): The password to use when authenticating with the remote origin.

        Raises:
            CustomException: If there is an error cloning the remote git repository to the local path.
        """
        remote_url = self._normalize_clone_url(remote_url)

        try:
            # Parse the remote URL.
            parsed = urlparse(remote_url)

            # Get the network location.
            auth_netloc = f"{user_name}:{user_pwd}@{parsed.netloc}"

            # Create a new ParseResult with the updated network location
            auth_parsed = parsed._replace(netloc=auth_netloc)
            auth_repo_url = urlunparse(auth_parsed)
        except Exception as e:
            logger.error(f"Failed to parse remote URL {remote_url}: {str(e)}")
            raise CustomException()
        
        # Clone the remote repository to the local path.
        try:
            Repo.clone_from(auth_repo_url, self.local_path)
        except GitCommandError as e:
            logger.error(f"Failed to clone remote repository from {remote_url} to {self.local_path}: {str(e)}")
            raise CustomException()