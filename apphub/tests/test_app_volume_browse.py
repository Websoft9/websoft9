import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.services.app_volume_browse import AppVolumeBrowseService


class FakeAuthService:
    def _require_authenticated_operator(self, session_token):
        if session_token != "valid-session":
            raise CustomException(401, "Authentication Required", "Login required")
        return {"id": "operator-1"}


class FakeVolume:
    def __init__(self, name="wordpress_data", project="wordpress"):
        self.attrs = {"Name": name, "Labels": {"com.docker.compose.project": project}}


class FakeContainer:
    def __init__(self, name="wordpress-web-1", project="wordpress", mounts=None, result=None):
        self.name = name
        self.attrs = {
            "Config": {"Labels": {"com.docker.compose.project": project}},
            "Mounts": mounts if mounts is not None else [{"Type": "volume", "Name": "wordpress_data", "Destination": "/var/www/html"}],
        }
        self.result = result or SimpleNamespace(exit_code=0, output=b"W9B1\x00R\x00drwxr-xr-x\x00www-data\x00www-data\x004096\x001700000001\x001700000002\x001700000003\x00F\x00index.php\x00-rw-r--r--\x00www-data\x00www-data\x00405\x001700000001\x001700000002\x001700000003\x00T\x00false\x00")
        self.commands = []

    def exec_run(self, command):
        self.commands.append(command)
        return self.result


class FakeDockerClient:
    def __init__(self, volume, containers):
        self.volumes = SimpleNamespace(get=lambda name: volume if name == volume.attrs["Name"] else (_ for _ in ()).throw(KeyError(name)))
        self.containers = SimpleNamespace(list=lambda filters: containers)


def build_service(volume=None, containers=None):
    return AppVolumeBrowseService(
        docker_client=FakeDockerClient(volume or FakeVolume(), containers or [FakeContainer()]),
        auth_service=FakeAuthService(),
    )


def test_lists_current_application_volume_with_stable_container_selection():
    first = FakeContainer(name="wordpress-z")
    selected = FakeContainer(name="wordpress-a")
    service = build_service(containers=[first, selected])

    response = service.list_directory("valid-session", "wordpress", "wordpress_data", "/")

    assert response["source_container"] == "wordpress-a"
    assert response["directory"]["path"] == "/"
    assert response["directory"]["item_type"] == "directory"
    assert response["items"] == [{"name": "index.php", "path": "/index.php", "item_type": "file", "size": 405, "mode": "-rw-r--r--", "owner": "www-data", "group": "www-data", "accessed_at": 1700000001, "modified_at": 1700000002, "created_at": 1700000003, "text_viewable": True}]
    assert selected.commands
    assert not first.commands


def test_parses_directory_records_from_container_response():
    directory, items, truncated = AppVolumeBrowseService._parse_directory_output(
        b"W9B1\x00R\x00drwxr-xr-x\x00www-data\x00www-data\x004096\x001700000001\x001700000002\x001700000003\x00D\x00uploads\x00drwxr-xr-x\x00www-data\x00www-data\x004096\x001700000001\x001700000002\x001700000003\x00T\x00false\x00",
        "/",
    )

    assert directory["path"] == "/"
    assert items == [{"name": "uploads", "path": "/uploads", "item_type": "directory", "size": 0, "mode": "drwxr-xr-x", "owner": "www-data", "group": "www-data", "accessed_at": 1700000001, "modified_at": 1700000002, "created_at": 1700000003, "text_viewable": False}]
    assert not truncated


def test_rejects_volume_outside_current_application():
    service = build_service(volume=FakeVolume(project="other-app"))

    with pytest.raises(CustomException) as error:
        service.list_directory("valid-session", "wordpress", "wordpress_data", "/")

    assert error.value.status_code == 403


def test_rejects_path_escape_before_container_exec():
    container = FakeContainer()
    service = build_service(containers=[container])

    with pytest.raises(CustomException) as error:
        service.list_directory("valid-session", "wordpress", "wordpress_data", "/../../etc")

    assert error.value.status_code == 400
    assert not container.commands


def test_passes_mount_root_to_container_exec_for_symlink_boundary_checks():
    container = FakeContainer()
    service = build_service(containers=[container])

    service.list_directory("valid-session", "wordpress", "wordpress_data", "/uploads")

    assert container.commands[0][-2:] == ["/var/www/html/uploads", "/var/www/html"]


def test_reads_only_utf8_text_and_rejects_binary_content():
    text_container = FakeContainer(result=SimpleNamespace(exit_code=0, output=b"hello\n"))
    service = build_service(containers=[text_container])
    response = service.read_text_file("valid-session", "wordpress", "wordpress_data", "/notes.txt")
    assert response["content"] == "hello\n"

    binary_container = FakeContainer(result=SimpleNamespace(exit_code=0, output=b"binary\x00payload"))
    binary_service = build_service(containers=[binary_container])
    with pytest.raises(CustomException) as error:
        binary_service.read_text_file("valid-session", "wordpress", "wordpress_data", "/notes.txt")
    assert error.value.status_code == 422


def test_rejects_multiple_mounts_in_one_container():
    container = FakeContainer(mounts=[
        {"Type": "volume", "Name": "wordpress_data", "Destination": "/one"},
        {"Type": "volume", "Name": "wordpress_data", "Destination": "/two"},
    ])
    service = build_service(containers=[container])

    with pytest.raises(CustomException) as error:
        service.list_directory("valid-session", "wordpress", "wordpress_data", "/")

    assert error.value.status_code == 422