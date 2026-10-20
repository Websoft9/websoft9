import ast
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException


@pytest.fixture
def cleanup():
    # Other backup tests replace the app_manager module at collection time.
    # Compile the real cleanup methods without importing its service dependencies.
    source = PROJECT_ROOT / "src/services/app_manager.py"
    tree = ast.parse(source.read_text())
    definition = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AppManger")
    definition.body = [
        node for node in definition.body
        if isinstance(node, ast.FunctionDef) and node.name in {"remove_error_app", "_cleanup_error_app_resources"}
    ]
    portainer = Mock()
    portainer.get_local_endpoint_id.return_value = 1
    portainer.get_stack_by_name.return_value = None
    portainer.get_containers_by_stack_name.return_value = []
    gitea = Mock()
    gitea.check_repo_exists.return_value = True
    proxy = Mock()
    proxy.get_proxy_host_by_app.return_value = [{"id": 42}]
    tasks = Mock(return_value=[("failed-task", {"app_id": "demo", "status": 4})])
    deleted = Mock()
    forgotten = Mock()
    namespace = {
        "CustomException": CustomException,
        "logger": Mock(),
        "PortainerManager": Mock(return_value=portainer),
        "GiteaManager": Mock(return_value=gitea),
        "ProxyManager": Mock(return_value=proxy),
        "list_install_tasks_readonly": tasks,
        "forget_install_secrets": forgotten,
        "remove_app_from_errors_by_app_id": deleted,
    }
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(source), "exec"), namespace)
    manager = object.__new__(namespace["AppManger"])
    return SimpleNamespace(
        manager=manager, portainer=portainer, gitea=gitea, proxy=proxy,
        tasks=tasks, deleted=deleted, forgotten=forgotten, namespace=namespace,
    )


@pytest.mark.parametrize("status", [1, 2, 0])
def test_cleanup_rejects_same_name_deployment_without_ownership(cleanup, status):
    cleanup.portainer.get_stack_by_name.return_value = {"Id": 9, "Status": status}
    with pytest.raises(CustomException, match="Invalid Request") as caught:
        cleanup.manager.remove_error_app("demo")
    assert "deployment" in caught.value.details
    cleanup.portainer.remove_stack_and_volumes.assert_not_called()
    cleanup.gitea.remove_repo.assert_not_called()
    cleanup.proxy.remove_proxy_host_by_app.assert_not_called()
    cleanup.deleted.assert_not_called()
    cleanup.forgotten.assert_not_called()


@pytest.mark.parametrize("state", ["running", "exited"])
def test_cleanup_rejects_external_deployment_with_stale_failure(cleanup, state):
    cleanup.portainer.get_containers_by_stack_name.return_value = [{"Id": "external", "State": state}]
    with pytest.raises(CustomException):
        cleanup.manager.remove_error_app("demo")
    cleanup.gitea.remove_repo.assert_not_called()
    cleanup.deleted.assert_not_called()


def test_cleanup_backend_rechecks_active_installation(cleanup):
    cleanup.tasks.return_value.append(("new-task", {"app_id": "demo", "status": 3}))
    with pytest.raises(CustomException) as caught:
        cleanup.manager.remove_error_app("demo")
    assert "active installation" in caught.value.details
    cleanup.namespace["PortainerManager"].assert_not_called()
    cleanup.deleted.assert_not_called()


@pytest.mark.parametrize("dependency", ["endpoint", "stack", "containers", "repo", "proxy"])
def test_cleanup_failure_retains_tracking_and_secrets(cleanup, dependency):
    failing_call = {
        "endpoint": cleanup.portainer.get_local_endpoint_id,
        "stack": cleanup.portainer.get_stack_by_name,
        "containers": cleanup.portainer.get_containers_by_stack_name,
        "repo": cleanup.gitea.remove_repo,
        "proxy": cleanup.proxy.remove_proxy_host_by_app,
    }[dependency]
    failing_call.side_effect = RuntimeError("dependency unavailable")
    with pytest.raises(CustomException) as caught:
        cleanup.manager.remove_error_app("demo")
    assert caught.value.status_code == 500
    assert "tracking retained" in caught.value.message
    cleanup.deleted.assert_not_called()
    cleanup.forgotten.assert_not_called()


def test_cleanup_retry_finishes_before_deleting_tracking(cleanup):
    cleanup.gitea.remove_repo.side_effect = RuntimeError("retry needed")
    with pytest.raises(CustomException):
        cleanup.manager.remove_error_app("demo")
    cleanup.deleted.assert_not_called()
    cleanup.gitea.remove_repo.side_effect = None
    cleanup.manager.remove_error_app("demo")
    cleanup.proxy.remove_proxy_host_by_app.assert_called_once_with("demo")
    cleanup.deleted.assert_called_once_with("demo")
    cleanup.forgotten.assert_called_once_with("demo")
    cleanup.tasks.assert_called_with((3, 4, 6), strict=True)


def test_cleanup_cli_reports_backend_failure(monkeypatch, cleanup):
    from src.cli.app_commands import app_group

    app_module = types.ModuleType("src.services.app_manager")
    app_module.AppManger = lambda: cleanup.manager
    status_module = types.ModuleType("src.services.app_status")
    status_module.list_install_tasks_readonly = Mock(return_value=[])
    monkeypatch.setitem(sys.modules, "src.services.app_manager", app_module)
    monkeypatch.setitem(sys.modules, "src.services.app_status", status_module)
    cleanup.gitea.remove_repo.side_effect = RuntimeError("dependency unavailable")
    result = CliRunner().invoke(app_group, ["clean-error", "demo", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["ok"] is False
    status_module.list_install_tasks_readonly.assert_called_once_with((3,), strict=True)
    cleanup.deleted.assert_not_called()


@pytest.fixture
def restore(monkeypatch):
    from src.services import back_manager as module

    manager = object.__new__(module.BackupManager)
    manager._ensure_repository = Mock()
    manager.list_snapshots = Mock(return_value=[
        {"id": "full-snapshot", "short_id": "snapshot", "paths": ["/demo_data"]},
    ])
    manager._run_restic_container = Mock(return_value='{"message_type":"summary"}')
    manager._resolve_host_path = lambda path: path
    app = SimpleNamespace(
        app_id="demo", endpointId=1, status=1,
        volumes=[{"Name": "demo_data", "Mountpoint": "/host/demo_data"}],
    )
    app_manager = SimpleNamespace(get_app_by_id=Mock(return_value=app))
    monkeypatch.setattr(module, "AppManger", lambda: app_manager)
    portainer = Mock()
    portainer.get_containers_by_stack_name.side_effect = [
        [{"Id": "runtime", "Names": ["/demo"], "State": "running"}],
        [{"Id": "runtime", "Names": ["/demo"], "State": "exited"}],
        [{"Id": "runtime", "Names": ["/demo"], "State": "running"}],
    ]
    monkeypatch.setattr(module, "PortainerManager", lambda: portainer)
    filesystem = SimpleNamespace(stat=Mock(return_value=SimpleNamespace(st_uid=0, st_gid=0)), chown=Mock())
    monkeypatch.setattr(module, "os", filesystem)
    return SimpleNamespace(
        manager=manager, app=app, app_manager=app_manager, portainer=portainer,
        module=module, filesystem=filesystem,
    )


@pytest.mark.parametrize("paths", [None, [], ["/old_data"], ["/demo_data", "/extra"], "/demo_data", [None]])
def test_restore_rejects_snapshot_mount_mismatch_before_stopping(restore, paths):
    restore.manager.list_snapshots.return_value[0]["paths"] = paths
    with pytest.raises(CustomException) as caught:
        restore.manager.restore_backup("demo", "snapshot")
    assert "paths do not match" in caught.value.message
    restore.portainer.stop_stack.assert_not_called()
    restore.manager._run_restic_container.assert_not_called()


def test_restore_rejects_partial_volume_mounts(restore):
    restore.app.volumes.append({"Name": "missing_mountpoint"})
    with pytest.raises(CustomException):
        restore.manager.restore_backup("demo", "snapshot")
    restore.portainer.stop_stack.assert_not_called()
    restore.manager._run_restic_container.assert_not_called()


@pytest.mark.parametrize("snapshot_id", ["snapshot", "full-snapshot"])
def test_restore_checks_quiescence_and_running_state(restore, snapshot_id):
    restore.manager.restore_backup("demo", snapshot_id)
    restore.portainer.stop_stack.assert_called_once_with("demo", 1)
    restore.manager._run_restic_container.assert_called_once_with(
        ["restore", snapshot_id, "--target", "/"],
        {"/host/demo_data": {"bind": "/demo_data", "mode": "rw"}},
    )
    restore.portainer.start_stack.assert_called_once_with("demo", 1)
    assert restore.portainer.get_containers_by_stack_name.call_count == 3


@pytest.mark.parametrize("attribute,value", [("status", 2), ("endpointId", None)])
def test_restore_rejects_inactive_or_unresolved_stack(restore, attribute, value):
    setattr(restore.app, attribute, value)
    with pytest.raises(CustomException):
        restore.manager.restore_backup("demo", "snapshot")
    restore.portainer.stop_stack.assert_not_called()
    restore.manager._run_restic_container.assert_not_called()


@pytest.mark.parametrize("containers", [[], [{"Names": ["/demo-init"], "State": "exited"}]])
def test_restore_rejects_missing_runtime_containers(restore, containers):
    restore.portainer.get_containers_by_stack_name.side_effect = [containers]
    with pytest.raises(CustomException):
        restore.manager.restore_backup("demo", "snapshot")
    restore.portainer.stop_stack.assert_not_called()
    restore.manager._run_restic_container.assert_not_called()


@pytest.mark.parametrize("state", ["running", "paused", "restarting", "unknown"])
def test_restore_requires_observed_quiescence(restore, state):
    restore.portainer.get_containers_by_stack_name.side_effect = [
        [{"Names": ["/demo"], "State": "running"}],
        [{"Names": ["/demo"], "State": state}],
    ]
    with pytest.raises(CustomException) as caught:
        restore.manager.restore_backup("demo", "snapshot")
    assert caught.value.details == "Restore Stop Failed"
    restore.manager._run_restic_container.assert_not_called()


@pytest.mark.parametrize("error", [RuntimeError("stop failed"), CustomException(400, "stop failed")])
def test_restore_stop_failure_never_writes_data(restore, error):
    restore.portainer.stop_stack.side_effect = error
    with pytest.raises(CustomException):
        restore.manager.restore_backup("demo", "snapshot")
    restore.manager._run_restic_container.assert_not_called()
    restore.portainer.start_stack.assert_not_called()


@pytest.mark.parametrize("output", ['{"message_type":"error","error":{"message":"restore failed"}}', ""])
def test_restore_restic_failure_does_not_report_success(restore, output):
    restore.manager._run_restic_container.return_value = output
    with pytest.raises(CustomException):
        restore.manager.restore_backup("demo", "snapshot")
    restore.portainer.start_stack.assert_not_called()


def test_restore_restart_error_is_not_swallowed(restore):
    restore.portainer.start_stack.side_effect = RuntimeError("restart failed")
    with pytest.raises(CustomException) as caught:
        restore.manager.restore_backup("demo", "snapshot")
    assert caught.value.details == "Restore Restart Failed"


@pytest.mark.parametrize("containers", [[], [{"Names": ["/demo"], "State": "exited"}]])
def test_restore_rejects_unsuccessful_restart(monkeypatch, restore, containers):
    restore.portainer.get_containers_by_stack_name.side_effect = [
        [{"Names": ["/demo"], "State": "running"}],
        [{"Names": ["/demo"], "State": "exited"}],
        containers,
    ]
    monkeypatch.setattr(restore.module, "time", SimpleNamespace(monotonic=Mock(side_effect=[0, 61]), sleep=Mock()))
    with pytest.raises(CustomException) as caught:
        restore.manager.restore_backup("demo", "snapshot")
    assert caught.value.details == "Restore Validation Failed"
    restore.portainer.start_stack.assert_called_once_with("demo", 1)


def test_restore_preserves_non_www_data_volume_owner(restore):
    restore.filesystem.stat.side_effect = [
        SimpleNamespace(st_uid=999, st_gid=999), SimpleNamespace(st_uid=0, st_gid=0),
    ]
    restore.manager.restore_backup("demo", "snapshot")
    restore.filesystem.chown.assert_called_once_with("/host/demo_data", 999, 999)


def test_backup_restore_cli_propagates_readiness_failure(monkeypatch, restore):
    from src.cli.backup_commands import backup_group

    app_module = types.ModuleType("src.services.app_manager")
    app_module.AppManger = lambda: restore.app_manager
    backup_module = types.ModuleType("src.services.back_manager")
    backup_module.BackupManager = lambda: restore.manager
    monkeypatch.setitem(sys.modules, "src.services.app_manager", app_module)
    monkeypatch.setitem(sys.modules, "src.services.back_manager", backup_module)
    restore.portainer.get_containers_by_stack_name.side_effect = [
        [{"Names": ["/demo"], "State": "running"}],
        [{"Names": ["/demo"], "State": "exited"}],
        [],
    ]
    monkeypatch.setattr(restore.module, "time", SimpleNamespace(monotonic=Mock(side_effect=[0, 61]), sleep=Mock()))
    result = CliRunner().invoke(backup_group, ["restore", "demo", "snapshot", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["ok"] is False
