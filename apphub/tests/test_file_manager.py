import base64
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.v1.routers import auth as auth_router
from src.api.v1.routers import files as files_router
from src.core.exception import CustomException
from src.schemas.errorResponse import ErrorResponse
from src.services.file_manager import DOCKER_VOLUMES_ROOT_SENTINEL, FileManagerService


DOCKER_VOLUMES_ROOT = "/var/lib/docker/volumes"
WORDPRESS_ROOT = f"{DOCKER_VOLUMES_ROOT}/wordpress_data/_data"
GITEA_ROOT = f"{DOCKER_VOLUMES_ROOT}/websoft9_gitea/_data"
ALT_DOCKER_VOLUMES_ROOT = "/srv/websoft9/volumes"
ALT_WORDPRESS_ROOT = f"{ALT_DOCKER_VOLUMES_ROOT}/wordpress_data/_data"
ALT_GITEA_ROOT = f"{ALT_DOCKER_VOLUMES_ROOT}/websoft9_gitea/_data"
MISSING_WORDPRESS_ROOT = "/missing/wordpress_data/_data"
MISSING_GITEA_ROOT = "/missing/websoft9_gitea/_data"


def create_test_app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(CustomException)
    async def custom_exception_handler(_request, exc: CustomException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(message=exc.message, details=exc.details).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, exc: RequestValidationError):
        errors = ", ".join(f"{err['loc'][1]}: {err['msg']}" for err in exc.errors())
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(message="Request Validation Error", details=errors).model_dump(),
        )

    app.include_router(auth_router.router)
    app.include_router(files_router.router)
    return app


class FakeVolume:
    def __init__(self, name: str, driver: str = "local", labels: Optional[dict] = None, mountpoint: Optional[str] = None):
        self.attrs = {"Name": name, "Driver": driver, "Labels": labels or {}}
        if mountpoint is not None:
            self.attrs["Mountpoint"] = mountpoint
        self.removed = False

    @property
    def name(self):
        return self.attrs["Name"]

    def remove(self, force: bool = False):
        self.removed = True


class FakeVolumes:
    def __init__(self, volumes):
        self._volumes = volumes

    def list(self):
        return [volume for volume in self._volumes if not volume.removed]

    def get(self, name: str):
        for volume in self._volumes:
            if volume.name == name and not volume.removed:
                return volume
        raise KeyError(name)


class FakeDockerClient:
    def __init__(self, volumes):
        self.volumes = FakeVolumes(volumes)

    def info(self):
        return {"DockerRootDir": "/var/lib/docker"}


class FakeFilesAgentExecutor:
    def __init__(self):
        self.directories = {
            WORDPRESS_ROOT: {
                "/": {
                    "metadata": {
                        "name": "wordpress_data",
                        "path": "/",
                        "item_type": "directory",
                        "size": 4096,
                        "mode": "drwx------",
                        "owner": "root",
                        "group": "root",
                        "accessed_at": "2026-04-29T11:11:21Z",
                        "modified_at": "2025-09-23T14:49:09Z",
                        "created_at": "2025-09-23T14:49:09Z",
                        "text_editable": False,
                    },
                    "items": [
                        {
                            "name": "config",
                            "path": "/config",
                            "item_type": "directory",
                            "size": 0,
                            "mode": "drwx------",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": False,
                        },
                        {
                            "name": "notes.txt",
                            "path": "/notes.txt",
                            "item_type": "file",
                            "size": 12,
                            "mode": "-rw-r--r--",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": True,
                        },
                    ],
                },
                "/config": {
                    "metadata": {
                        "name": "config",
                        "path": "/config",
                        "item_type": "directory",
                        "size": 4096,
                        "mode": "drwx------",
                        "owner": "root",
                        "group": "root",
                        "accessed_at": "2026-04-29T11:11:21Z",
                        "modified_at": "2026-04-29T10:00:00Z",
                        "created_at": "2026-04-29T09:00:00Z",
                        "text_editable": False,
                    },
                    "items": [],
                },
            },
            ALT_WORDPRESS_ROOT: {
                "/": {
                    "metadata": {
                        "name": "wordpress_data",
                        "path": "/",
                        "item_type": "directory",
                        "size": 4096,
                        "mode": "drwx------",
                        "owner": "root",
                        "group": "root",
                        "accessed_at": "2026-04-29T11:11:21Z",
                        "modified_at": "2025-09-23T14:49:09Z",
                        "created_at": "2025-09-23T14:49:09Z",
                        "text_editable": False,
                    },
                    "items": [
                        {
                            "name": "config",
                            "path": "/config",
                            "item_type": "directory",
                            "size": 0,
                            "mode": "drwx------",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": False,
                        },
                        {
                            "name": "notes.txt",
                            "path": "/notes.txt",
                            "item_type": "file",
                            "size": 12,
                            "mode": "-rw-r--r--",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": True,
                        },
                    ],
                },
            },
            MISSING_WORDPRESS_ROOT: {
                "/": {
                    "metadata": {
                        "name": "wordpress_data",
                        "path": "/",
                        "item_type": "directory",
                        "size": 4096,
                        "mode": "drwx------",
                        "owner": "root",
                        "group": "root",
                        "accessed_at": "2026-04-29T11:11:21Z",
                        "modified_at": "2025-09-23T14:49:09Z",
                        "created_at": "2025-09-23T14:49:09Z",
                        "text_editable": False,
                    },
                    "items": [
                        {
                            "name": "config",
                            "path": "/config",
                            "item_type": "directory",
                            "size": 0,
                            "mode": "drwx------",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": False,
                        },
                        {
                            "name": "notes.txt",
                            "path": "/notes.txt",
                            "item_type": "file",
                            "size": 12,
                            "mode": "-rw-r--r--",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": True,
                        },
                    ],
                },
            },
            DOCKER_VOLUMES_ROOT: {
                "/": {
                    "metadata": {
                        "name": "volumes",
                        "path": "/",
                        "item_type": "directory",
                        "size": 4096,
                        "mode": "drwx------",
                        "owner": "root",
                        "group": "root",
                        "accessed_at": "2026-04-29T11:11:21Z",
                        "modified_at": "2025-09-23T14:49:09Z",
                        "created_at": "2025-09-23T14:49:09Z",
                        "text_editable": False,
                    },
                    "items": [
                        {
                            "name": "custom_ssl",
                            "path": "/custom_ssl",
                            "item_type": "directory",
                            "size": 0,
                            "mode": "drwx------",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": False,
                        },
                        {
                            "name": "credential.json",
                            "path": "/credential.json",
                            "item_type": "file",
                            "size": 64,
                            "mode": "-rw-------",
                            "owner": "root",
                            "group": "root",
                            "accessed_at": "2026-04-29T11:11:21Z",
                            "modified_at": "2026-04-29T10:00:00Z",
                            "created_at": "2026-04-29T09:00:00Z",
                            "text_editable": True,
                        },
                    ],
                }
            },
            ALT_GITEA_ROOT: {
                "/": {
                    "metadata": {
                        "name": "websoft9_gitea",
                        "path": "/",
                        "item_type": "directory",
                        "size": 4096,
                        "mode": "drwx------",
                        "owner": "root",
                        "group": "root",
                        "accessed_at": "2026-04-29T11:11:21Z",
                        "modified_at": "2025-09-23T14:49:09Z",
                        "created_at": "2025-09-23T14:49:09Z",
                        "text_editable": False,
                    },
                    "items": [],
                },
            },
        }
        self.contents = {(WORDPRESS_ROOT, "/notes.txt"): "hello world\n"}
        self.downloads = {(WORDPRESS_ROOT, "/notes.txt"): b"hello world\n"}
        self.metadata = {
            (WORDPRESS_ROOT, "/"): {
                "name": "wordpress_data",
                "path": "/",
                "item_type": "directory",
                "size": 4096,
                "mode": "drwx------",
                "owner": "root (0)",
                "group": "root (0)",
                "accessed_at": "2026-04-29T11:11:21Z",
                "modified_at": "2025-09-23T14:49:09Z",
                "created_at": "2025-09-23T14:49:09Z",
                "text_editable": False,
            },
            (WORDPRESS_ROOT, "/notes.txt"): {
                "name": "notes.txt",
                "path": "/notes.txt",
                "item_type": "file",
                "size": 12,
                "mode": "-rw-r--r--",
                "owner": "root (0)",
                "group": "root (0)",
                "accessed_at": "2026-04-29T11:11:21Z",
                "modified_at": "2026-04-29T10:00:00Z",
                "created_at": "2026-04-29T09:00:00Z",
                "text_editable": True,
            },
            (ALT_WORDPRESS_ROOT, "/"): {
                "name": "wordpress_data",
                "path": "/",
                "item_type": "directory",
                "size": 4096,
                "mode": "drwx------",
                "owner": "root (0)",
                "group": "root (0)",
                "accessed_at": "2026-04-29T11:11:21Z",
                "modified_at": "2025-09-23T14:49:09Z",
                "created_at": "2025-09-23T14:49:09Z",
                "text_editable": False,
            },
            (MISSING_WORDPRESS_ROOT, "/"): {
                "name": "wordpress_data",
                "path": "/",
                "item_type": "directory",
                "size": 4096,
                "mode": "drwx------",
                "owner": "root (0)",
                "group": "root (0)",
                "accessed_at": "2026-04-29T11:11:21Z",
                "modified_at": "2025-09-23T14:49:09Z",
                "created_at": "2025-09-23T14:49:09Z",
                "text_editable": False,
            },
            (DOCKER_VOLUMES_ROOT, "/"): {
                "name": "volumes",
                "path": "/",
                "item_type": "directory",
                "size": 4096,
                "mode": "drwx------",
                "owner": "root (0)",
                "group": "root (0)",
                "accessed_at": "2026-04-29T11:11:21Z",
                "modified_at": "2025-09-23T14:49:09Z",
                "created_at": "2025-09-23T14:49:09Z",
                "text_editable": False,
            },
        }
        self.last_metadata_call: Optional[tuple[str, str, str]] = None

    def list_directory(self, root_path: str, relative_path: str, display_name: str):
        return self.directories[root_path][relative_path]

    def read_text_file(self, root_path: str, relative_path: str, display_name: str):
        return self.contents[(root_path, relative_path)]

    def get_metadata(self, root_path: str, relative_path: str, display_name: str):
        self.last_metadata_call = (root_path, relative_path, display_name)
        return self.metadata[(root_path, relative_path)]

    def write_text_file(self, root_path: str, relative_path: str, content: str, display_name: str):
        self.contents[(root_path, relative_path)] = content
        self.downloads[(root_path, relative_path)] = content.encode("utf-8")

    def create_directory(self, root_path: str, relative_path: str, display_name: str):
        self.directories.setdefault(root_path, {}).setdefault(relative_path, {"metadata": {}, "items": []})

    def create_empty_file(self, root_path: str, relative_path: str, display_name: str):
        self.contents[(root_path, relative_path)] = ""
        self.downloads[(root_path, relative_path)] = b""

    def rename_path(self, root_path: str, source_relative_path: str, target_relative_path: str, display_name: str):
        self.contents[(root_path, target_relative_path)] = self.contents.pop((root_path, source_relative_path), "")
        self.downloads[(root_path, target_relative_path)] = self.downloads.pop((root_path, source_relative_path), b"")

    def delete_path(self, root_path: str, relative_path: str, display_name: str):
        self.contents.pop((root_path, relative_path), None)
        self.downloads.pop((root_path, relative_path), None)

    def upload_file(self, root_path: str, parent_relative_path: str, file_name: str, payload: bytes, display_name: str):
        base = parent_relative_path.rstrip("/")
        path = f"{base}/{file_name}" if base else f"/{file_name}"
        self.contents[(root_path, path)] = payload.decode("utf-8")
        self.downloads[(root_path, path)] = payload

    def download_file(self, root_path: str, relative_path: str, display_name: str):
        return self.downloads[(root_path, relative_path)]


def build_service(*, with_mountpoint: bool = True) -> FileManagerService:
    docker_client = FakeDockerClient(
        [
            FakeVolume(
                "wordpress_data",
                labels={"com.docker.compose.project": "wordpress"},
                mountpoint=WORDPRESS_ROOT if with_mountpoint else None,
            ),
            FakeVolume(
                "websoft9_gitea",
                labels={"owner": "websoft9"},
                mountpoint=GITEA_ROOT if with_mountpoint else None,
            ),
        ]
    )
    return FileManagerService(docker_client=docker_client, helper_executor=FakeFilesAgentExecutor())


def authenticate(client: TestClient):
    response = client.post(
        "/auth/initialize",
        json={"username": "admin", "password": "StrongPass123!", "display_name": "Platform Admin"},
    )
    assert response.status_code == 200


def test_file_manager_lists_volumes_and_browse_root(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))
    service = build_service()
    monkeypatch.setattr(files_router, "_get_file_manager_service", lambda: service)

    with TestClient(create_test_app()) as client:
        authenticate(client)

        volumes_response = client.get("/files/volumes")
        assert volumes_response.status_code == 200
        payload = volumes_response.json()
        assert [item["volume_name"] for item in payload["volumes"]] == ["websoft9_gitea", "wordpress_data", "platform-gateway-certificates"]

        browse_response = client.get("/files/tree", params={"volume_id": "wordpress_data", "path": "/"})
        assert browse_response.status_code == 200
        browse_payload = browse_response.json()
        assert browse_payload["volume_name"] == "wordpress_data"
        assert [item["name"] for item in browse_payload["items"]] == ["config", "notes.txt"]

        metadata_response = client.get("/files/metadata", params={"volume_id": "wordpress_data", "path": "/"})
        assert metadata_response.status_code == 200
        metadata_payload = metadata_response.json()
        assert metadata_payload["mode"] == "drwx------"
        assert metadata_payload["owner"] == "root (0)"
        assert metadata_payload["group"] == "root (0)"

        root_metadata_response = client.get("/files/root-metadata")
        assert root_metadata_response.status_code == 200
        assert root_metadata_response.json()["name"] == "volumes"

        root_tree_response = client.get("/files/root-tree")
        assert root_tree_response.status_code == 200
        root_tree_payload = root_tree_response.json()
        assert [item["name"] for item in root_tree_payload["items"]] == ["custom_ssl", "credential.json"]


def test_file_manager_text_edit_upload_download_and_mutations(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))
    service = build_service()
    monkeypatch.setattr(files_router, "_get_file_manager_service", lambda: service)

    with TestClient(create_test_app()) as client:
        authenticate(client)

        content_response = client.get("/files/content", params={"volume_id": "wordpress_data", "path": "/notes.txt"})
        assert content_response.status_code == 200
        assert content_response.json()["content"] == "hello world\n"

        file_metadata_response = client.get("/files/metadata", params={"volume_id": "wordpress_data", "path": "/notes.txt"})
        assert file_metadata_response.status_code == 200
        assert file_metadata_response.json()["text_editable"] is True

        save_response = client.put(
            "/files/content",
            json={"volume_id": "wordpress_data", "path": "/notes.txt", "content": "updated\n"},
        )
        assert save_response.status_code == 200
        assert save_response.json()["path"] == "/notes.txt"

        create_folder_response = client.post(
            "/files/folders",
            json={"volume_id": "wordpress_data", "parent_path": "/", "name": "uploads"},
        )
        assert create_folder_response.status_code == 200

        create_file_response = client.post(
            "/files/items",
            json={"volume_id": "wordpress_data", "parent_path": "/", "name": "draft.txt"},
        )
        assert create_file_response.status_code == 200

        rename_response = client.post(
            "/files/rename",
            json={"volume_id": "wordpress_data", "source_path": "/draft.txt", "target_name": "draft-renamed.txt"},
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["path"] == "/draft-renamed.txt"

        upload_response = client.post(
            "/files/upload",
            json={
                "volume_id": "wordpress_data",
                "parent_path": "/",
                "file_name": "upload.txt",
                "content_base64": base64.b64encode(b"payload").decode("utf-8"),
            },
        )
        assert upload_response.status_code == 200

        download_response = client.get("/files/download", params={"volume_id": "wordpress_data", "path": "/upload.txt"})
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/octet-stream"

        delete_response = client.request(
            "DELETE",
            "/files/item",
            json={"volume_id": "wordpress_data", "path": "/draft-renamed.txt"},
        )
        assert delete_response.status_code == 200

        delete_volume_response = client.request(
            "DELETE",
            "/files/item",
            json={"volume_id": "websoft9_gitea", "path": "/"},
        )
        assert delete_volume_response.status_code == 200
        assert delete_volume_response.json()["operation"] == "delete-volume"


def test_file_manager_supports_root_scope_mutations(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))
    service = build_service()
    monkeypatch.setattr(files_router, "_get_file_manager_service", lambda: service)

    with TestClient(create_test_app()) as client:
        authenticate(client)

        create_folder_response = client.post(
            "/files/folders",
            json={"volume_id": DOCKER_VOLUMES_ROOT_SENTINEL, "parent_path": "/", "name": "root-scratch"},
        )
        assert create_folder_response.status_code == 200
        assert create_folder_response.json()["volume_name"] == ""

        browse_root_subdirectory_response = client.get(
            "/files/tree",
            params={"volume_id": DOCKER_VOLUMES_ROOT_SENTINEL, "path": "/root-scratch"},
        )
        assert browse_root_subdirectory_response.status_code == 200
        assert browse_root_subdirectory_response.json()["current_path"] == "/root-scratch"

        create_file_response = client.post(
            "/files/items",
            json={"volume_id": DOCKER_VOLUMES_ROOT_SENTINEL, "parent_path": "/", "name": "root-note.txt"},
        )
        assert create_file_response.status_code == 200

        upload_response = client.post(
            "/files/upload",
            json={
                "volume_id": DOCKER_VOLUMES_ROOT_SENTINEL,
                "parent_path": "/",
                "file_name": "root-upload.txt",
                "content_base64": base64.b64encode(b"root payload").decode("utf-8"),
            },
        )
        assert upload_response.status_code == 200

        delete_response = client.request(
            "DELETE",
            "/files/item",
            json={"volume_id": DOCKER_VOLUMES_ROOT_SENTINEL, "path": "/root-upload.txt"},
        )
        assert delete_response.status_code == 200

        delete_root_response = client.request(
            "DELETE",
            "/files/item",
            json={"volume_id": DOCKER_VOLUMES_ROOT_SENTINEL, "path": "/"},
        )
        assert delete_root_response.status_code == 400
        assert "cannot be deleted" in delete_root_response.json()["details"].lower()


def test_file_manager_rejects_unauthenticated_and_path_escape_requests(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))
    service = build_service()
    monkeypatch.setattr(files_router, "_get_file_manager_service", lambda: service)

    with TestClient(create_test_app()) as client:
        unauthenticated_response = client.get("/files/volumes")
        assert unauthenticated_response.status_code == 401

        authenticate(client)

        escape_response = client.get("/files/tree", params={"volume_id": "wordpress_data", "path": "/../../etc"})
        assert escape_response.status_code == 400
        assert "outside the allowed volume root" in escape_response.json()["details"].lower()

        invalid_upload_response = client.post(
            "/files/upload",
            json={
                "volume_id": "wordpress_data",
                "parent_path": "/",
                "file_name": "broken.txt",
                "content_base64": "not-valid-base64",
            },
        )
        assert invalid_upload_response.status_code == 400
        assert "content_base64 must be valid base64" in invalid_upload_response.json()["details"]


def test_file_manager_falls_back_to_docker_root_when_mountpoint_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))
    service = build_service(with_mountpoint=False)
    monkeypatch.setattr(files_router, "_get_file_manager_service", lambda: service)

    with TestClient(create_test_app()) as client:
        authenticate(client)
        metadata_response = client.get("/files/metadata", params={"volume_id": "wordpress_data", "path": "/"})
        assert metadata_response.status_code == 200
        assert service.helper_executor.last_metadata_call == (WORDPRESS_ROOT, "/", "wordpress_data")


def test_file_manager_uses_volume_mountpoint_when_host_path_is_not_locally_accessible(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(tmp_path))

    docker_client = FakeDockerClient(
        [
            FakeVolume(
                "wordpress_data",
                labels={"com.docker.compose.project": "wordpress"},
                mountpoint=MISSING_WORDPRESS_ROOT,
            ),
            FakeVolume(
                "websoft9_gitea",
                labels={"owner": "websoft9"},
                mountpoint=MISSING_GITEA_ROOT,
            ),
        ]
    )
    service = FileManagerService(docker_client=docker_client, helper_executor=FakeFilesAgentExecutor())
    monkeypatch.setattr(files_router, "_get_file_manager_service", lambda: service)

    with TestClient(create_test_app()) as client:
        authenticate(client)
        metadata_response = client.get("/files/metadata", params={"volume_id": "wordpress_data", "path": "/"})
        assert metadata_response.status_code == 200
        assert service.helper_executor.last_metadata_call == (MISSING_WORDPRESS_ROOT, "/", "wordpress_data")