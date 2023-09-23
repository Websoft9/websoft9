import os
import shutil
from git import Repo, GitCommandError
from src.core.exception import CustomException
from src.core.logger import logger
from urllib.parse import urlparse, urlunparse

class GitManager:
    """
    This class is used to interact with Git

    Attributes:
        local_path (str): The path to the local git repository.

    Methods:
        init_local_repo_from_dir() -> None: Initialize a local git repository from a directory.
        push_local_repo_to_remote_repo(remote_url:str,user_name:str,user_pwd:str) -> None: Push a local git repository to a remote origin.
        remove_git_directory() -> None: Remove the .git directory.
    """

    def __init__(self,local_path:str):
        """
        Initialize the GitManager instance
        """
        self.local_path = local_path

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
        
        # Parse the remote URL.
        parsed = urlparse(remote_url)

        # Get the network location.
        auth_netloc = f"{user_name}:{user_pwd}@{parsed.netloc}"

        # Create a new ParseResult with the updated network location
        auth_parsed = parsed._replace(netloc=auth_netloc)
        auth_repo_url = urlunparse(auth_parsed)

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
        
    