import json
import os
import sys
import threading
import types
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))

git_module = types.ModuleType('git')
git_module.Repo = object
sys.modules.setdefault('git', git_module)

jwt_module = types.ModuleType('jwt')
sys.modules.setdefault('jwt', jwt_module)

keyring_module = types.ModuleType('keyring')
keyring_module.get_password = lambda *args, **kwargs: None
keyring_module.set_password = lambda *args, **kwargs: None
sys.modules.setdefault('keyring', keyring_module)

docker_module = types.ModuleType('docker')
docker_module.from_env = lambda: None
sys.modules.setdefault('docker', docker_module)

app_manager_module = types.ModuleType('src.services.app_manager')
app_manager_module.AppManger = object
sys.modules.setdefault('src.services.app_manager', app_manager_module)

portainer_manager_module = types.ModuleType('src.services.portainer_manager')
portainer_manager_module.PortainerManager = object
sys.modules.setdefault('src.services.portainer_manager', portainer_manager_module)

from src.core.exception import CustomException
from src.services import back_manager as back_manager_module
from src.services.back_manager import BackupManager


class FakePortainer:
    def __init__(self, stack_status, container_sequences, stack_status_sequence=None):
        self.stack_status = stack_status
        self.stack_status_sequence = list(stack_status_sequence or [])
        self.container_sequences = list(container_sequences)
        self.up_calls = []
        self.start_calls = []
        self.stop_calls = []

    def get_stack_by_name(self, app_id, endpoint_id):
        if self.stack_status_sequence:
            status = self.stack_status_sequence.pop(0)
        else:
            status = self.stack_status
        return {"Id": 9, "Name": app_id, "Status": status}

    def stop_stack(self, app_id, endpoint_id):
        self.stop_calls.append((app_id, endpoint_id))

    def up_stack(self, stack_id, endpoint_id):
        self.up_calls.append((stack_id, endpoint_id))

    def start_stack(self, app_id, endpoint_id):
        self.start_calls.append((app_id, endpoint_id))

    def get_containers_by_stack_name(self, app_id, endpoint_id):
        if self.container_sequences:
            return self.container_sequences.pop(0)
        return []


def _build_manager():
    manager = object.__new__(BackupManager)
    manager.docker_client = None
    # The manager is normally created through __init__, which resolves these two values.
    manager.repository_path = "/var/lib/websoft9/backup/restic-repo"
    manager.restic_image = "restic/restic:latest"
    return manager


def test_bootstrap_repository_ensures_image_before_repository(monkeypatch):
    manager = _build_manager()
    steps = []

    monkeypatch.setattr(manager, '_ensure_restic_image', lambda: steps.append('image'))
    monkeypatch.setattr(manager, '_ensure_repository', lambda: steps.append('repository'))

    manager.bootstrap_repository()

    assert steps == ['image', 'repository']


def test_restore_starts_containers_after_restore(monkeypatch):
    manager = _build_manager()
    portainer = FakePortainer(
        stack_status=1,
        container_sequences=[[
            {"Names": ["/wordpress_demo"], "State": "running"},
        ]],
    )

    monkeypatch.setattr(manager, '_ensure_repository', lambda: None)
    monkeypatch.setattr(manager, 'list_snapshots', lambda app_id, use_cache=True: [{"id": "snap-1", "short_id": "snap-1"}])
    monkeypatch.setattr(manager, '_run_restic_container', lambda command, extra_volumes: '{"message_type":"summary"}')
    monkeypatch.setattr(back_manager_module, 'AppManger', lambda: types.SimpleNamespace(
        get_app_by_id=lambda app_id: types.SimpleNamespace(
            endpointId=1,
            volumes=[{"Mountpoint": "/var/lib/docker/volumes/wordpress_demo/_data", "Name": "wordpress_demo"}],
        )
    ))
    monkeypatch.setattr(back_manager_module, 'PortainerManager', lambda: portainer)
    monkeypatch.setattr(manager, '_resolve_host_path', lambda path: path)

    manager.restore_backup('wordpress_demo', 'snap-1')

    assert portainer.stop_calls == [('wordpress_demo', 1)]
    assert portainer.up_calls == []
    assert portainer.start_calls == [('wordpress_demo', 1)]


def test_restore_validation_rejects_only_exited_runtime_containers(monkeypatch):
    manager = _build_manager()
    portainer = FakePortainer(
        stack_status=1,
        container_sequences=[[
            {"Names": ["/wordpress_demo-init"], "State": "exited"},
            {"Names": ["/wordpress_demo"], "State": "exited"},
            {"Names": ["/wordpress_demo-mysql"], "State": "exited"},
        ]],
    )

    monkeypatch.setattr(back_manager_module.time, 'sleep', lambda _: None)

    try:
        manager._ensure_restored_app_running(portainer, 'wordpress_demo', 1, timeout_seconds=0, poll_interval=0)
    except CustomException as exc:
        assert exc.status_code == 500
        assert 'did not reach a running state' in exc.message
    else:
        raise AssertionError('Expected restore validation to fail for exited runtime containers')


def test_restore_validation_accepts_running_runtime_container(monkeypatch):
    manager = _build_manager()
    portainer = FakePortainer(
        stack_status=1,
        container_sequences=[[
            {"Names": ["/wordpress_demo-init"], "State": "exited"},
            {"Names": ["/wordpress_demo"], "State": "running"},
            {"Names": ["/wordpress_demo-mysql"], "State": "exited"},
        ]],
    )

    monkeypatch.setattr(back_manager_module.time, 'sleep', lambda _: None)

    manager._ensure_restored_app_running(portainer, 'wordpress_demo', 1, timeout_seconds=0, poll_interval=0)


def test_build_restic_volume_mounts_resolves_host_mountpoints(monkeypatch):
    manager = _build_manager()
    monkeypatch.setattr(manager, '_resolve_host_path', lambda path: path.replace('/var/lib/docker/volumes', '/host-volumes'))

    extra_volumes, container_paths = manager._build_restic_volume_mounts([
        {"Mountpoint": "/var/lib/docker/volumes/wordpress_demo/_data", "Name": "wordpress_demo"},
        {"Mountpoint": "/var/lib/docker/volumes/wordpress_demo_db/_data", "Name": "wordpress_demo_db"},
    ])

    assert container_paths == ['/wordpress_demo', '/wordpress_demo_db']
    assert extra_volumes == {
        '/host-volumes/wordpress_demo/_data': {'bind': '/wordpress_demo', 'mode': 'rw'},
        '/host-volumes/wordpress_demo_db/_data': {'bind': '/wordpress_demo_db', 'mode': 'rw'},
    }


def test_repo_operations_use_restic_container_runner(monkeypatch, tmp_path):
    manager = _build_manager()
    manager.repository_path = str(tmp_path / "repo")
    os.makedirs(manager.repository_path)
    (tmp_path / "repo" / "config").write_text("{}")
    commands = []

    def fake_run_restic_container(command, extra_volumes):
        commands.append((command, extra_volumes))
        if command == ['snapshots', '--tag', 'wordpress_demo']:
            return '[{"id":"snap-1","short_id":"snap-1"}]'
        if command == ['forget', 'snap-1']:
            return ''
        raise AssertionError(f'unexpected command: {command}')

    monkeypatch.setattr(manager, '_run_restic_container', fake_run_restic_container)
    back_manager_module._repository_ready_cache.clear()
    back_manager_module._snapshot_list_cache.clear()

    snapshots = manager.list_snapshots('wordpress_demo')
    manager.delete_snapshot('snap-1')

    assert snapshots == [{"id": "snap-1", "short_id": "snap-1"}]
    assert commands == [
        (['snapshots', '--tag', 'wordpress_demo'], {}),
        (['forget', 'snap-1'], {}),
    ]


def test_snapshot_list_is_served_from_cache_until_refreshed(monkeypatch, tmp_path):
    """Listing starts a restic container, so repeated reads reuse a short-lived cache."""
    manager = _build_manager()
    manager.repository_path = str(tmp_path / "repo")
    os.makedirs(manager.repository_path)
    (tmp_path / "repo" / "config").write_text("{}")
    commands = []
    snapshots = [{"id": "snap-1", "short_id": "snap-1"}]

    def fake_run_restic_container(command, extra_volumes):
        commands.append(command)
        if command[:1] == ['snapshots']:
            return json.dumps(snapshots)
        if command[:1] == ['forget']:
            return ''
        raise AssertionError(f'unexpected command: {command}')

    monkeypatch.setattr(manager, '_run_restic_container', fake_run_restic_container)
    back_manager_module._repository_ready_cache.clear()
    back_manager_module._snapshot_list_cache.clear()

    assert manager.list_snapshots('wordpress_demo') == snapshots
    first_round = list(commands)

    # Second read: no restic call at all.
    assert manager.list_snapshots('wordpress_demo') == snapshots
    assert commands == first_round

    # An explicit refresh goes back to the repository.
    assert manager.list_snapshots('wordpress_demo', use_cache=False) == snapshots
    assert commands[-1] == ['snapshots', '--tag', 'wordpress_demo']

    # A mutation drops the cache so the next read is accurate.
    manager.delete_snapshot('snap-1')
    before_read = len(commands)
    assert manager.list_snapshots('wordpress_demo') == snapshots
    assert len(commands) > before_read


def test_repository_readiness_is_cached_from_local_config(monkeypatch, tmp_path):
    """Repeated readiness checks use the repository config marker, not a restic container."""
    manager = _build_manager()
    manager.repository_path = str(tmp_path / "repo")
    os.makedirs(manager.repository_path)
    (tmp_path / "repo" / "config").write_text("{}")
    commands = []

    def fake_run_restic_container(command, extra_volumes):
        commands.append(command)
        raise AssertionError("existing repository should not run a readiness command")

    monkeypatch.setattr(manager, '_run_restic_container', fake_run_restic_container)
    back_manager_module._repository_ready_cache.clear()

    manager._ensure_repository()
    manager._ensure_repository()
    manager._ensure_repository()

    assert commands == []


def test_concurrent_repository_initialization_runs_once(monkeypatch, tmp_path):
    manager = _build_manager()
    manager.repository_path = str(tmp_path / "repo")
    initialization_started = threading.Event()
    release_initialization = threading.Event()
    initialized = []

    def fake_init_repository():
        initialized.append(True)
        initialization_started.set()
        assert release_initialization.wait(timeout=1)
        os.makedirs(manager.repository_path)
        (tmp_path / "repo" / "config").write_text("{}")

    monkeypatch.setattr(manager, '_init_repository', fake_init_repository)
    back_manager_module._repository_ready_cache.clear()

    first = threading.Thread(target=manager._ensure_repository)
    second = threading.Thread(target=manager._ensure_repository)
    first.start()
    assert initialization_started.wait(timeout=1)
    second.start()
    release_initialization.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert initialized == [True]


def test_repository_initialization_uses_a_parent_directory_lock(monkeypatch, tmp_path):
    manager = _build_manager()
    manager.repository_path = str(tmp_path / "repo")
    initialized = []

    def fake_init_repository():
        initialized.append(True)
        os.makedirs(manager.repository_path)
        (tmp_path / "repo" / "config").write_text("{}")

    monkeypatch.setattr(manager, '_init_repository', fake_init_repository)
    back_manager_module._repository_ready_cache.clear()

    manager._ensure_repository()

    assert initialized == [True]
    assert (tmp_path / ".restic-repository-init.lock").is_file()


def test_snapshot_list_does_not_recache_results_invalidated_while_loading(monkeypatch):
    manager = _build_manager()
    loading_started = threading.Event()
    release_loading = threading.Event()

    monkeypatch.setattr(manager, '_ensure_repository', lambda: None)
    back_manager_module._snapshot_list_cache.clear()

    def fake_run_restic_repo_command(_command):
        loading_started.set()
        assert release_loading.wait(timeout=1)
        return '[{"id": "stale-snapshot"}]'

    monkeypatch.setattr(manager, '_run_restic_repo_command', fake_run_restic_repo_command)

    request = threading.Thread(target=manager.list_snapshots, args=('wordpress_demo',))
    request.start()
    assert loading_started.wait(timeout=1)
    back_manager_module._invalidate_snapshot_cache()
    release_loading.set()
    request.join(timeout=1)

    cache_key = f'{manager.repository_path}:wordpress_demo'
    assert cache_key not in back_manager_module._snapshot_list_cache


def test_backup_manager_defaults_restic_image_when_missing_from_system_config(monkeypatch):
    class FakeConfigManager:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_value(self, section, key):
            if (section, key) == ('volume_backup', 'repopath'):
                return '/opt/websoft9/data/backup/restic-repo'
            if (section, key) == ('volume_backup', 'image'):
                raise Exception('missing image key')
            raise AssertionError(f'unexpected config lookup: {(section, key)}')

    fake_docker_client = types.SimpleNamespace()
    manager = object.__new__(BackupManager)

    monkeypatch.setattr(back_manager_module, 'ConfigManager', FakeConfigManager)
    monkeypatch.setattr(back_manager_module.docker, 'from_env', lambda: fake_docker_client)
    monkeypatch.setattr(back_manager_module.os, 'makedirs', lambda *args, **kwargs: None)
    monkeypatch.setattr(BackupManager, '_init_repository', lambda self: None)

    BackupManager.__init__(manager)

    assert manager.restic_image == 'restic/restic:latest'