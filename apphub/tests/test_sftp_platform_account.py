from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.services import app_sftp_acl, app_sftp_prepare
from src.services.sftp_path_authorization import AppVolumeResolver, bind_volume_id, rejected_path, split_volume_id


def container(name, mounts, user="999:999", stat_output=None):
    def exec_run(command, **kwargs):
        if stat_output is None:
            return SimpleNamespace(exit_code=1, output=b"")
        return SimpleNamespace(exit_code=0, output=stat_output.encode("utf-8"))

    return SimpleNamespace(
        name=name,
        status="running",
        attrs={"Config": {"User": user}, "Mounts": mounts},
        exec_run=exec_run,
    )


def docker_client(containers, volumes=None):
    return SimpleNamespace(
        containers=SimpleNamespace(list=lambda filters=None: containers),
        volumes=SimpleNamespace(get=lambda identifier: SimpleNamespace(attrs=volumes[identifier])),
    )


def test_volume_identifiers_round_trip():
    assert split_volume_id("data") == ("volume", "data")
    assert split_volume_id("volume:data") == ("volume", "data")
    identifier = bind_volume_id("/srv/example")
    assert split_volume_id(identifier) == ("bind", identifier.split(":", 1)[1])


@pytest.mark.parametrize("path", ["/", "/etc", "/etc/ssh", "/var/lib/docker/volumes", "/root/data"])
def test_protected_paths_are_rejected(path):
    assert rejected_path(path)


@pytest.mark.parametrize("path", ["/srv/app", "/home/ubuntu/www", "/data/example"])
def test_application_paths_are_allowed(path):
    assert not rejected_path(path)


def test_named_volume_data_directory_is_allowed():
    assert not rejected_path("/var/lib/docker/volumes/example/_data")
    assert rejected_path("/var/lib/docker/volumes")


def test_resolver_rejects_volume_of_another_application():
    resolver = AppVolumeResolver(docker_client=docker_client(
        [container("app-1", [{"Type": "volume", "Name": "data", "Source": "/var/lib/docker/volumes/data/_data"}])],
        {"data": {"Driver": "local", "Options": {}, "Mountpoint": "/var/lib/docker/volumes/data/_data", "Labels": {"com.docker.compose.project": "other"}}},
    ))
    with pytest.raises(CustomException) as error:
        resolver.resolve("example", "data")
    assert error.value.status_code == 403


def test_resolver_supports_bind_mount_and_container_identity():
    source = "/srv/example"
    resolver = AppVolumeResolver(docker_client=docker_client(
        [container("app-1", [{"Type": "bind", "Source": source, "Destination": "/data"}])],
        {},
    ))
    target = resolver.resolve("example", bind_volume_id(source))
    assert target["source_path"] == source
    assert target["container_uid"] == 999
    assert target["container_name"] == "app-1"


def test_resolver_rejects_missing_volume():
    resolver = AppVolumeResolver(docker_client=docker_client([container("app-1", [])], {}))
    with pytest.raises(CustomException) as error:
        resolver.resolve("example", "data")
    assert error.value.status_code == 404


def test_resolver_probes_container_identity_when_image_declares_no_user():
    source = "/srv/wordpress"
    resolver = AppVolumeResolver(docker_client=docker_client(
        [container(
            "app-1",
            [{"Type": "bind", "Source": source, "Destination": "/var/www/html"}],
            user="",
            stat_output="33:33\n",
        )],
        {},
    ))
    target = resolver.resolve("example", bind_volume_id(source))
    assert target["container_uid"] == 33
    assert target["container_gid"] == 33


def test_resolver_keeps_unknown_identity_when_probe_fails():
    source = "/srv/distroless"
    resolver = AppVolumeResolver(docker_client=docker_client(
        [container(
            "app-1",
            [{"Type": "bind", "Source": source, "Destination": "/data"}],
            user="",
            stat_output=None,
        )],
        {},
    ))
    target = resolver.resolve("example", bind_volume_id(source))
    assert target["container_uid"] == 0


def test_acl_entries_grant_the_container_user_default_access(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(app_sftp_acl, "setfacl", lambda arguments, timeout=30: calls.append(arguments))
    app_sftp_acl.apply_entries(str(tmp_path), "websoft9-sftp", 33)
    entries = calls[0][1]
    assert "u:websoft9-sftp:rwX" in entries
    assert "d:u:websoft9-sftp:rwX" in entries
    assert "d:u:33:rwX" in entries
    assert "d:m:rwX" in entries


def test_sshd_config_uses_a_shared_group_umask():
    assert "ForceCommand internal-sftp -u 0002" in app_sftp_prepare.SSHD_BLOCK


def test_acl_helper_maps_host_paths_through_the_mount(monkeypatch, tmp_path):
    root = tmp_path / "host"
    root.mkdir()
    monkeypatch.setenv("WEBSOFT9_HOST_ROOT", str(root))
    mounted = str(root / "var/lib/example")
    assert app_sftp_acl.fs_path("/var/lib/example") == mounted
    assert app_sftp_acl.fs_path(mounted) == mounted
    assert app_sftp_acl.host_view(mounted) == "/var/lib/example"
    assert app_sftp_acl.host_view("/var/lib/example") == "/var/lib/example"


def test_acl_helper_without_host_mount_keeps_plain_paths(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_HOST_ROOT", "/nonexistent-host-root")
    assert app_sftp_acl.fs_path("/var/lib/example") == "/var/lib/example"
    assert app_sftp_acl.host_view("/var/lib/example") == "/var/lib/example"


def test_acl_validate_target_resolves_through_the_host_mount(monkeypatch, tmp_path):
    root = tmp_path / "host"
    (root / "srv/app").mkdir(parents=True)
    monkeypatch.setenv("WEBSOFT9_HOST_ROOT", str(root))
    assert app_sftp_acl.validate_target("/srv/app") == "/srv/app"


def test_acl_helpers_detect_traverse_and_ancestors(tmp_path):
    access, default = app_sftp_acl.parse_acl(
        "user::rwx\nuser:websoft9-sftp:rwx\nmask::rwx\nother::---\n"
    )
    assert app_sftp_acl.has_traverse(access, "websoft9-sftp") is True
    assert app_sftp_acl.has_traverse(default, "websoft9-sftp") is False
    assert app_sftp_acl.ancestor_paths(str(tmp_path / "a/b"))[-1] == str(tmp_path / "a")


def test_acl_target_validation_rejects_root_and_symlinks(tmp_path):
    with pytest.raises(ValueError):
        app_sftp_acl.validate_target("/")
    target = tmp_path / "data"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        app_sftp_acl.validate_target(str(link))
    assert app_sftp_acl.validate_target(str(target)) == str(target.resolve())
