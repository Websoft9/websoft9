import json
import os
import re
import docker
import configparser
import requests
from datetime import datetime
from typing import List, Dict, Optional
from src.core.exception import CustomException
from src.core.logger import logger
from src.core.config import ConfigManager
from src.services.app_manager import AppManger

class BackupManager:
    """Docker Volume Backup Manager using Restic"""

    def __init__(self):
        """Initialize BackupManager"""
        try:
            self.docker_client = docker.from_env()
            
            # Load backup repository path from config
            config_manager = ConfigManager("system.ini")
            self.repository_path = config_manager.get_value("volume_backup", "repopath")
            self.hostname = config_manager.get_value("volume_backup", "hostname")
            self.restic_image = config_manager.get_value("volume_backup", "image")        
            
            # Initialize repository if needed
            self._init_repository()         
        except Exception as e:
            logger.error(f"Failed to initialize BackupManager: {e}")
            raise CustomException()
    

    def _ensure_image_with_mirrors(self):
        """
        Ensure the restic image exists locally. If not, attempt to pull the image using mirrors.
        """
        try:
            # Check if the image already exists locally
            self.docker_client.images.get(self.restic_image)
            return
        except docker.errors.ImageNotFound:
            logger.access(f"Image {self.restic_image} not found locally. Attempting to pull...")
        except Exception as e:
            logger.error(f"Unexpected error while checking image {self.restic_image}: {e}")
            raise CustomException(500, f"Unexpected error while checking image {self.restic_image}: {e}", "Image Check Error")

        # Attempt to pull the image directly
        try:
            self.docker_client.images.pull(self.restic_image)
            return
        except Exception as e:
            logger.error(f"Direct pull of image {self.restic_image} failed, Begin mirror pull")

        # Load mirrors from a remote URL
        try:
            config_manager = ConfigManager("config.ini")
            mirrors_url = config_manager.get_value("docker_mirror", "url")
            response = requests.get(mirrors_url)
            if response.status_code != 200:
                logger.error(f"Failed to download image accelerators: {response.text}")
                raise CustomException(500, "Failed to download image accelerators", "Mirror Configuration Error")
            mirrors = response.json().get("mirrors", [])
        except Exception as e:
            logger.error(f"Failed to fetch Docker mirrors: {e}")
            raise CustomException(500, "Failed to fetch Docker mirrors", "Mirror Fetch Error")

        # Attempt to pull the image using mirrors
        for mirror in mirrors:
            try:
                mirrored_image = f"{mirror}/{self.restic_image}"
                self.docker_client.images.pull(mirrored_image)

                # Rename the image tag back to the original tag
                self.docker_client.images.get(mirrored_image).tag(self.restic_image)
                self.docker_client.images.remove(mirrored_image, force=True)  # Remove the mirrored tag
                logger.access(f"Successfully pulled image {mirrored_image} using mirror.")
                return
            except Exception as e:
                logger.error(f"Pulling image {mirrored_image} using mirror failed: {e}")

        # If all attempts fail, raise an exception
        logger.error(f"Failed to pull image {self.restic_image} using all mirrors.")
        raise CustomException(500, f"Failed to pull image {self.restic_image} using all mirrors", "Image Pull Error")


    def _check_repository(self) -> bool:
        """
        Check if repository is initialized by reading config

        Returns:
            bool: True if repository exists and is accessible, False otherwise
        """
        try:
            volumes = {self.repository_path: {'bind': '/repo', 'mode': 'rw'}}
            command = ['-r', '/repo', 'cat', 'config', '--insecure-no-password', '--json']
            
            output = self._run_container(command, volumes)
            
            # Parse repository config JSON
            try:
                config = json.loads(output)
                return bool(config.get('id') and config.get('version'))
            except (json.JSONDecodeError, KeyError):
                return False
        except CustomException:
            return False
        except Exception as e:
            logger.error(f"Repository check error: {e}")
            return False


    def _init_repository(self):
        """
        Initialize restic repository if needed

        Generated command:
        docker run --rm --hostname {hostname from config} \
        -v {repository_path}:/repo \
        restic/restic -r /repo init --insecure-no-password --json
        """
        try:
            # First check if repository already exists
            if self._check_repository():
                return
                    
            volumes = {self.repository_path: {'bind': '/repo', 'mode': 'rw'}}
            command = ['-r', '/repo', 'init', '--insecure-no-password', '--json']
            
            output = self._run_container(command, volumes)
            
            # Simple validation of initialization
            try:
                result = json.loads(output)
                if result.get('message_type') != 'initialized':
                    logger.error(f"Unexpected initialization response: {result}")
            except (json.JSONDecodeError, KeyError):
                pass           
        except CustomException as e:
            logger.error(f"Repository initialization failed: {e}")
            raise CustomException()
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            raise CustomException()


    def _run_container(self, command: List[str], volumes: Dict[str, Dict[str, str]], remove: bool = True) -> str:
        self._ensure_image_with_mirrors()  # Ensure the image exists before running the container
        try:
            container = self.docker_client.containers.run(
                image=self.restic_image,
                command=command,
                volumes=volumes,
                hostname=self.hostname,
                remove=remove,  
                detach=False,
                stdout=True,
                stderr=True
            )
            result = container.decode('utf-8') if isinstance(container, bytes) else str(container)
            return result
            
        except docker.errors.ContainerError as e:
            # Container exited with non-zero status, let caller handle the specific logic
            error_output = e.stderr.decode('utf-8') if e.stderr else str(e)
            error_message = json.loads(error_output).get("message", "Unknown error")
            raise CustomException(500, error_message, "Internal Server Error")
        except Exception as e:
            raise CustomException(500, "Run container failed", "Internal Server Error")


    def create_backup(self, app_id: str) -> Dict:
        """
        Create backup for an app by app_id. 自动从 app_manager 获取挂载卷信息。

        Args:
            app_id: Application ID

        Returns:
            Backup result dict
        """
        try:
            # 自动获取 volume_mappings
            app_info = AppManger().get_app_by_id(app_id)
            volumes_info = getattr(app_info, "volumes", [])
            volume_mappings = {}
            for v in volumes_info:
                mountpoint = v.get("Mountpoint")
                name = v.get("Name")
                if mountpoint and name:
                    volume_mappings[mountpoint] = f"/{name}"

            # Ensure repository is initialized
            if not self._check_repository():
                logger.error("Repository not initialized. Attempting to initialize...")
                self._init_repository()

            # Prepare volumes - repository mount is always required
            volumes = {self.repository_path: {'bind': '/repo', 'mode': 'rw'}}
            backup_paths = []

            # Add data volumes from volume_mappings (这些是需要备份的路径)
            for host_path, container_path in volume_mappings.items():
                volumes[host_path] = {'bind': container_path, 'mode': 'rw'}
                backup_paths.append(container_path)

            # Build command - follow the working format
            command = ['-r', '/repo', 'backup'] + backup_paths + ['--json']
            command.extend(['--tag', app_id])
            command.append('--insecure-no-password')

            # Execute backup
            output = self._run_container(command, volumes)

            # Check if backup was successful
            try:
                for line in output.strip().split('\n'):
                    if line.strip():
                        json_data = json.loads(line)
                        if json_data.get('message_type') == 'summary' and 'snapshot_id' in json_data:
                            logger.access(f"Backup successful for app: {app_id}")
                            return
            except Exception as e:
                logger.error(f"Error parsing backup output: {e}")
            logger.error(f"Backup failed for app: {app_id}")
            raise CustomException(f"Backup failed for app: {app_id}")
        except CustomException as e:
            logger.error(f"Backup failed for app: {app_id}, error: {e}")
            raise CustomException()
        except Exception as e:
            logger.error(f"Backup error for app: {app_id}, error: {e}")
            raise CustomException()

    def list_snapshots(self, app_id: str = None) -> List[Dict]:
        """List snapshots filtered by app_id"""
        try:
            # Ensure repository is initialized
            if not self._check_repository():
                logger.error("Repository not initialized. Cannot list snapshots.")
                raise CustomException(400, "Repository not initialized", "Repository Error")
            
            # Prepare volumes and command
            volumes = {self.repository_path: {'bind': '/repo', 'mode': 'rw'}}
            command = ['-r', '/repo', 'snapshots', '--json', '--insecure-no-password']

            # Add app_id to the command if provided
            if app_id:
                command.extend(['--tag', app_id])

            # Execute the command
            output = self._run_container(command, volumes)

            # Parse JSON output
            snapshots = json.loads(output) if output.strip() else []

            return snapshots

        except CustomException as e:
            logger.error(f"List snapshots failed: {e}")
            raise CustomException(f"Failed to list snapshots: {e}")
        except Exception as e:
            logger.error(f"List snapshots error: {e}")
            raise CustomException(f"Unexpected error while listing snapshots: {e}")

    def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a snapshot by its ID"""
        try:
            # Ensure repository is initialized
            if not self._check_repository():
                logger.error("Repository not initialized. Cannot delete snapshot.")
                raise CustomException(400, "Repository not initialized", "Repository Error")
            
            volumes = {self.repository_path: {'bind': '/repo', 'mode': 'rw'}}
            command = ['-r', '/repo', 'forget', snapshot_id, '--insecure-no-password', '--json']
            
            output = self._run_container(command, volumes)
            
            # If no output, assume success
            if not output.strip():
                return
            
            # If output exists, treat it as an error
            logger.error(f"Delete snapshot failed: {output}")
            raise CustomException(status_code=400, message=f"Delete snapshot failed: {output}", details=f"Snapshot ID: {snapshot_id}")
            
        except CustomException as e:
            logger.error(f"Delete snapshot error: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while deleting snapshot {snapshot_id}: {e}")
            raise CustomException()

    def restore_backup(self, app_id: str,snapshot_id: str) -> None:
        """
        Restore backup to specified location.

        Args:
            snapshot_id (str): Snapshot ID to restore.
            app_id (str): Application ID to restore to.

        Raises:
            CustomException: If restore fails or mappings are not provided.
        """
        try:
            logger.access(f"Restoring snapshot: {snapshot_id}")

            # Ensure repository is initialized
            if not self._check_repository():
                logger.error("Repository not initialized. Cannot restore backup.")
                raise CustomException(400, "Repository not initialized", "Repository Error")

            # 自动获取 restore_mappings
            app_info = AppManger().get_app_by_id(app_id)
            volumes_info = getattr(app_info, "volumes", [])
            restore_mappings = {}
            for v in volumes_info:
                mountpoint = v.get("Mountpoint")
                name = v.get("Name")
                if mountpoint and name:
                    restore_mappings[mountpoint] = f"/{name}"

            # Prepare volumes for the restore operation
            volumes = {self.repository_path: {'bind': '/repo', 'mode': 'rw'}}
            for host_path, container_path in restore_mappings.items():
                volumes[host_path] = {'bind': container_path, 'mode': 'rw'}

            # Build the restore command
            command = ['-r', '/repo', 'restore', snapshot_id, '--target', '/', '--insecure-no-password', '--json']

            # Execute the restore command
            output = self._run_container(command, volumes)

            # Parse the output to check for success
            for line in output.strip().split('\n'):
                if line.strip():
                    try:
                        json_data = json.loads(line)
                        if json_data.get('message_type') == 'summary':
                            logger.access(f"Snapshot {snapshot_id} restored successfully")
                            return
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON output during restore: {line}")
                        raise CustomException(500, f"Invalid output during restore: {line}", "Internal Server Error")

            # If no summary message is found, assume failure
            logger.error(f"Restore failed for snapshot: {snapshot_id}")
            raise CustomException(500, f"Restore failed for snapshot: {snapshot_id}", "Internal Server Error")
        except CustomException as e:
            logger.error(f"Restore snapshot failed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while restoring snapshot {snapshot_id}: {e}")
            raise CustomException()