import base64
import os
from git import Repo
from src.core.logger import logger
from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.external.gitea_api import GiteaAPI


class GiteaManager:
    def __init__(self):
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
        username = ConfigManager().get_value("gitea", "user_name")
        password = ConfigManager().get_value("gitea", "user_pwd")
          
        credentials = f"{username}:{password}"
        credentials_encoded = base64.b64encode(credentials.encode()).decode()
        self.gitea.set_credential(credentials_encoded)

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
            logger.error(f"Error validate repo is exist from gitea: {response.text}")
            raise CustomException()
        
    def create_repo(self, repo_name: str):
        """
        Create repository

        Args:
            repo_name (str): Repository name

        Returns:
            bool: True if repo is created, raise exception if repo is not created
        """
        response = self.gitea.create_repo(repo_name)
        if response.status_code == 201:
            return True
        else:
            logger.error(f"Error create repo from gitea: {response.text}")
            raise CustomException()
        
    def create_local_repo_and_push_remote(self, local_git_path: str,remote_git_url: str):
        if os.path.exists(local_git_path):
            try:
                repo = Repo.init(local_git_path)
                repo.create_head('main')
                repo.git.add(A=True)
                repo.index.commit("Initial commit")
                origin = repo.create_remote('origin',remote_git_url)
                origin.push(refspec='main:main')
            except Exception as e:
                logger.error(f"Error create local repo and push remote: {e}")
                raise CustomException()
        else:
            logger.error(f"Error repo path not exist: {local_git_path}")
            raise CustomException()
        
    def get_file_content_from_repo(self, repo_name: str, file_path: str):
        response = self.gitea.get_file_content_from_repo(repo_name, file_path)
        if response.status_code == 200:
            return {
                "name": response.json()["name"],
                "encoding": response.json()["encoding"],
                "sha": response.json()["sha"],
                "content": response.json()["content"],
            }
        else:
            logger.error(f"Error get file content from repo from gitea: {response.text}")
            raise CustomException()

    def update_file_in_repo(self, repo_name: str, file_path: str, content: str,sha: str):
        response = self.gitea.update_file_content_in_repo(repo_name, file_path, content, sha)
        if response.status_code == 201:
            return True
        else:
            logger.error(f"Error update file in repo from gitea: {response.text}")
            raise CustomException()
        
    def remove_repo(self, repo_name: str):
        response = self.gitea.remove_repo(repo_name)
        if response.status_code == 204:
            return True
        else:
            logger.error(f"Error remove repo from gitea: {response.text}")
            raise CustomException()