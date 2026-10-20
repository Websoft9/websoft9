from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from click.testing import CliRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_docker_frame(stream_id: int, text: str) -> bytes:
    payload = text.encode("utf-8")
    header = bytes([stream_id, 0, 0, 0]) + len(payload).to_bytes(4, "big")
    return header + payload


def test_app_diagnose_aggregates_oom_and_logs(monkeypatch):
    from src.cli.app_commands import app_group
    from src.schemas.appResponse import AppResponse

    class FakeAppManger:
        def get_app_by_id(self, app_id, endpoint_id=None, **kwargs):
            return AppResponse(
                app_id=app_id,
                endpointId=1,
                app_name="wordpress",
                app_official=True,
                status=4,
                error="Container exited unexpectedly",
                containers=[
                    {"Id": "cid111", "Names": [f"/{app_id}"], "Image": "wordpress:6", "State": "exited", "Status": "Exited (137)"},
                ],
                volumes=[],
            )

    class FakePortainerAPI:
        def read_container_logs_bounded(self, endpoint_id, container_id, params, max_bytes=524288, timeout_seconds=15):
            return _make_docker_frame(2, "Fatal error with DB_PASSWORD=mysecret\n"), False

    class FakePortainerManager:
        def __init__(self):
            self.portainer = FakePortainerAPI()

        def get_container_by_id(self, endpoint_id, container_id):
            return {
                "Id": container_id,
                "RestartCount": 3,
                "State": {"Status": "exited", "ExitCode": 137, "OOMKilled": True},
            }

    app_mgr_mod = types.ModuleType("src.services.app_manager")
    app_mgr_mod.AppManger = FakeAppManger
    monkeypatch.setitem(sys.modules, "src.services.app_manager", app_mgr_mod)

    pm_mod = types.ModuleType("src.services.portainer_manager")
    pm_mod.PortainerManager = FakePortainerManager
    monkeypatch.setitem(sys.modules, "src.services.portainer_manager", pm_mod)

    runner = CliRunner()
    res = runner.invoke(app_group, ["diagnose", "wp_oom", "--lines", "40", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    codes = {f["code"] for f in payload["data"]["findings"]}
    assert "APP_ERROR_STATE" in codes
    assert "CONTAINER_OOM_KILLED" in codes
    assert "mysecret" not in res.output


def test_app_exit_lifecycle_commands(monkeypatch):
    from src.cli.app_commands import app_group
    from src.schemas.appResponse import AppResponse

    calls = []

    class FakeAppManger:
        def uninstall_app(self, app_id, purge_data=False, endpointId=None):
            calls.append(("uninstall", app_id, purge_data, endpointId))

        def remove_app(self, app_id, endpointId=None):
            calls.append(("remove", app_id, endpointId))

        def remove_error_app(self, app_id):
            calls.append(("clean-error", app_id))

        async def redeploy_app(self, app_id, pull_image, endpointId=None):
            calls.append(("restore-redeploy", app_id, pull_image, endpointId))

        def get_app_by_id(self, app_id, endpoint_id=None, **kwargs):
            return AppResponse(
                app_id=app_id,
                endpointId=1,
                app_name="wordpress",
                app_official=True,
                status=2,
                volumes=[{"Name": f"{app_id}_data"}],
            )

    app_mgr_mod = types.ModuleType("src.services.app_manager")
    app_mgr_mod.AppManger = FakeAppManger
    monkeypatch.setitem(sys.modules, "src.services.app_manager", app_mgr_mod)
    monkeypatch.setattr("src.services.app_status.list_install_tasks_readonly", lambda statuses, strict=False: [])

    runner = CliRunner()
    uninst = runner.invoke(app_group, ["uninstall", "wp_1", "--keep-data", "--yes", "--json"])
    assert uninst.exit_code == 0
    assert json.loads(uninst.output)["data"]["resulting_state"] == "inactive"

    rest = runner.invoke(app_group, ["restore", "wp_1", "--yes", "--json"])
    assert rest.exit_code == 0
    assert json.loads(rest.output)["data"]["action"] == "restore"

    rem = runner.invoke(app_group, ["remove", "wp_1", "--purge-data", "--yes", "--json"])
    assert rem.exit_code == 0
    assert json.loads(rem.output)["data"]["purged_volumes"] == ["wp_1_data"]

    cln = runner.invoke(app_group, ["clean-error", "wp_err", "--yes", "--json"])
    assert cln.exit_code == 0
    assert ("clean-error", "wp_err") in calls


def test_git_log_diff_rm_and_rollback_cli(monkeypatch):
    from src.cli.git_commands import git_group

    class FakeGiteaManager:
        def list_repo_commits(self, repo_name, limit=20):
            return [{"sha": "abcdef1234567890", "short_sha": "abcdef1234", "message": "Update port", "author": "admin", "date": "2026-10-20T00:00:00Z"}]

        def get_repo_diff(self, repo_name, target_ref=None, base_ref=None):
            return {"repo": repo_name, "base": base_ref, "target": target_ref or "abcdef1234", "diff": "+DB_PASSWORD=topsecret\n"}

        def delete_repo_file(self, repo_name, file_path, sha=None):
            return {"path": file_path, "deleted_sha": sha, "head_sha": "newhead123"}

        def rollback_repo_to_commit(self, repo_name, target_commit):
            return {"app_id": repo_name, "target_commit": target_commit, "previous_head_sha": "oldhead", "new_head_sha": "newhead", "changed": True}

    gm_mod = types.ModuleType("src.services.gitea_manager")
    gm_mod.GiteaManager = FakeGiteaManager
    monkeypatch.setitem(sys.modules, "src.services.gitea_manager", gm_mod)

    runner = CliRunner()
    log_res = runner.invoke(git_group, ["log", "wp_1", "--json"])
    assert log_res.exit_code == 0
    assert json.loads(log_res.output)["data"]["items"][0]["short_sha"] == "abcdef1234"

    diff_res = runner.invoke(git_group, ["diff", "wp_1", "--json"])
    assert diff_res.exit_code == 0
    assert "topsecret" not in diff_res.output
    assert "******" in json.loads(diff_res.output)["data"]["diff"]

    # Protected file deletion must be blocked
    prot_rm = runner.invoke(git_group, ["rm", "wp_1", "docker-compose.yml", "--sha", "s1", "--yes", "--json"])
    assert prot_rm.exit_code == 1
    assert json.loads(prot_rm.output)["code"] == "INVALID_REQUEST"

    ok_rm = runner.invoke(git_group, ["rm", "wp_1", "src/extra.conf", "--sha", "s1", "--yes", "--json"])
    assert ok_rm.exit_code == 0
    assert json.loads(ok_rm.output)["data"]["path"] == "src/extra.conf"

    rb_res = runner.invoke(git_group, ["rollback", "wp_1", "--to", "abcdef1234", "--yes", "--json"])
    assert rb_res.exit_code == 0
    assert json.loads(rb_res.output)["data"]["changed"] is True


def test_backup_restore_safety_and_cli(monkeypatch):
    from src.cli.backup_commands import backup_group
    from src.core.exception import CustomException
    from src.schemas.appResponse import AppResponse
    from src.services import back_manager as back_manager_module
    from src.services.back_manager import BackupManager

    # 1. Verify BackupManager.restore_backup aborts if stop_stack fails
    manager = object.__new__(BackupManager)
    manager.docker_client = None
    manager.repository_path = "/mock/repo"
    manager.restic_image = "restic/restic:latest"

    restic_called = []
    monkeypatch.setattr(manager, "_ensure_repository", lambda: None)
    monkeypatch.setattr(manager, "list_snapshots", lambda app_id, use_cache=True: [{"id": "snap-1", "short_id": "snap-1", "paths": ["/wp_data"]}])
    monkeypatch.setattr(manager, "_run_restic_container", lambda cmd, vols: restic_called.append(cmd) or '{"message_type":"summary"}')
    monkeypatch.setattr(manager, "_resolve_host_path", lambda p: p)
    monkeypatch.setattr(
        back_manager_module,
        "AppManger",
        lambda: types.SimpleNamespace(
            get_app_by_id=lambda app_id, **kw: AppResponse(
                app_id=app_id,
                endpointId=1,
                volumes=[{"Mountpoint": "/mock/vol1", "Name": "wp_data"}],
            )
        ),
    )

    class FailingStopPortainer:
        def get_containers_by_stack_name(self, app_id, endpoint_id):
            return [{"Id": "runtime", "Names": [f"/{app_id}"], "State": "running"}]

        def stop_stack(self, app_id, endpoint_id):
            raise RuntimeError("Docker daemon busy")

    monkeypatch.setattr(back_manager_module, "PortainerManager", FailingStopPortainer)
    try:
        manager.restore_backup("wp_1", "snap-1")
    except CustomException as exc:
        assert "Failed to stop containers" in exc.message
    else:
        raise AssertionError("Expected restore_backup to abort when stop_stack fails")
    assert restic_called == []

    # 2. Verify CLI backup restore command requires --yes and succeeds with --yes
    app_mgr_mod = types.ModuleType("src.services.app_manager")
    app_mgr_mod.AppManger = lambda: types.SimpleNamespace(
        get_app_by_id=lambda app_id, **kw: AppResponse(
            app_id=app_id,
            endpointId=1,
            volumes=[{"Name": "wp_data"}],
        )
    )
    monkeypatch.setitem(sys.modules, "src.services.app_manager", app_mgr_mod)

    bm_mod = types.ModuleType("src.services.back_manager")
    bm_mod.BackupManager = lambda: types.SimpleNamespace(restore_backup=lambda app_id, snap_id: None)
    monkeypatch.setitem(sys.modules, "src.services.back_manager", bm_mod)

    runner = CliRunner()
    no_yes = runner.invoke(backup_group, ["restore", "wp_1", "snap-1", "--json"])
    assert no_yes.exit_code == 1
    assert json.loads(no_yes.output)["code"] == "CONFIRMATION_REQUIRED"

    ok_res = runner.invoke(backup_group, ["restore", "wp_1", "snap-1", "--yes", "--json"])
    assert ok_res.exit_code == 0, ok_res.output
    assert json.loads(ok_res.output)["data"]["status"] == "restored"


def test_docker_control_plane_protection_and_host_env_check_cli(monkeypatch):
    from src.cli.docker_commands import docker_group
    from src.cli.host_commands import host_group

    class FakePortainerManager:
        def get_local_endpoint_id(self):
            return 1

        def get_containers(self, endpoint_id):
            return [
                {"Id": "c-ctrl", "Names": ["/websoft9-apphub"], "Labels": {"com.docker.compose.project": "websoft9"}},
            ]

        def get_volumes(self, endpoint_id, dangling=False):
            return [
                {"Name": "wp_inactive_data", "Driver": "local", "Labels": {"com.docker.compose.project": "wp_inactive"}},
            ]

        def get_stacks(self, endpoint_id):
            return [{"Id": 5, "Name": "wp_inactive", "Status": 2}]

    pm_mod = types.ModuleType("src.services.portainer_manager")
    pm_mod.PortainerManager = FakePortainerManager
    monkeypatch.setitem(sys.modules, "src.services.portainer_manager", pm_mod)

    runner = CliRunner()
    # Stopping a control-plane container must be denied
    stop_ctrl = runner.invoke(docker_group, ["container", "stop", "websoft9-apphub", "--yes", "--json"])
    assert stop_ctrl.exit_code == 1
    assert json.loads(stop_ctrl.output)["code"] == "PERMISSION_DENIED"

    # Deleting a volume belonging to an inactive retained stack must be rejected
    del_vol = runner.invoke(docker_group, ["volume", "delete", "wp_inactive_data", "--yes", "--json"])
    assert del_vol.exit_code == 1
    assert json.loads(del_vol.output)["code"] == "INVALID_REQUEST"

    # host env-check
    env_res = runner.invoke(host_group, ["env-check", "--json"])
    assert env_res.exit_code == 0, env_res.output
    env_payload = json.loads(env_res.output)
    assert env_payload["ok"] is True
    assert "swap" in env_payload["data"]["checks"]
    assert "filesystem" in env_payload["data"]["checks"]
    assert "kernel" in env_payload["data"]["checks"]
    assert "dns" in env_payload["data"]["checks"]


def test_click_parameter_errors_emit_json_envelope_and_update_compose(monkeypatch, tmp_path):
    from src.cli.apphub_cli import cli

    runner = CliRunner()
    for bad_args in (
        ["app", "list", "--limit", "0", "--json"],
        ["app", "inspect", "--json"],
        ["docker", "container", "logs", "cid", "--tail", "0", "--json"],
        ["service", "logs", "unknown-svc", "--json"],
    ):
        res = runner.invoke(cli, bad_args)
        assert res.exit_code == 2, f"{bad_args} -> {res.output}"
        payload = json.loads(res.output)
        assert payload["ok"] is False
        assert payload["code"] == "INVALID_ARGUMENT"
        assert payload["data"] is None

    # Legacy command parameter error should remain Click plain text (not JSON envelope)
    legacy_bad = runner.invoke(cli, ["app", "install", "--unknown-flag", "--json"])
    assert legacy_bad.exit_code == 2
    assert not legacy_bad.output.strip().startswith("{")

    # Test app update-compose merges existing env and preserves mounts
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services:\n  web:\n    image: nginx:alpine\n", encoding="utf-8")

    captured = {}

    class FakeComposeAppManager:
        def get_compose_content(self, app_id):
            return {
                "app_id": app_id,
                "compose_content": "services:\n  web:\n    image: nginx:1.25\n",
                "env": [{"key": "EXISTING_KEY", "value": "existing_val"}, {"key": "PORT", "value": "80"}],
                "mounts": [{"path": "src/nginx.conf", "content": "worker_processes 1;"}],
            }

        def update_compose_content(self, app_id, compose_content, env, mounts, endpoint_id=None):
            captured["app_id"] = app_id
            captured["env"] = env
            captured["mounts"] = mounts

    cam_mod = types.ModuleType("src.services.compose_app_manager")
    cam_mod.ComposeAppManager = FakeComposeAppManager
    monkeypatch.setitem(sys.modules, "src.services.compose_app_manager", cam_mod)

    upd_res = runner.invoke(
        cli,
        ["app", "update-compose", "mycomp_1", "--file", str(compose_file), "--env", "PORT=8080", "--yes", "--json"],
    )
    assert upd_res.exit_code == 0, upd_res.output
    upd_payload = json.loads(upd_res.output)
    assert upd_payload["ok"] is True
    assert upd_payload["data"]["preserved_mounts"] == ["src/nginx.conf"]
    assert {e["key"]: e["value"] for e in captured["env"]} == {"EXISTING_KEY": "existing_val", "PORT": "8080"}
