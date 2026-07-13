import sys
import types
from pathlib import Path

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
    def __init__(self, stack_status, container_sequences):
        self.stack_status = stack_status
        self.container_sequences = list(container_sequences)
        self.up_calls = []
        self.start_calls = []

    def get_stack_by_name(self, app_id, endpoint_id):
        return {"Id": 9, "Name": app_id, "Status": self.stack_status}

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
    return manager


def test_restore_validation_uses_up_stack_for_inactive_stack(monkeypatch):
    manager = _build_manager()
    portainer = FakePortainer(
        stack_status=2,
        container_sequences=[[
            {"Names": ["/wordpress_demo-init"], "State": "exited"},
            {"Names": ["/wordpress_demo"], "State": "running"},
        ]],
    )

    monkeypatch.setattr(back_manager_module.time, 'sleep', lambda _: None)

    manager._ensure_restored_app_running(portainer, 'wordpress_demo', 1, timeout_seconds=0, poll_interval=0)
    stack_info = portainer.get_stack_by_name('wordpress_demo', 1)
    if stack_info.get('Status') == 2:
        portainer.up_stack(stack_info['Id'], 1)

    assert portainer.up_calls == [(9, 1)]
    assert portainer.start_calls == []


def test_restore_start_uses_start_stack_for_active_stack(monkeypatch):
    manager = _build_manager()
    portainer = FakePortainer(
        stack_status=1,
        container_sequences=[[
            {"Names": ["/wordpress_demo"], "State": "running"},
        ]],
    )

    monkeypatch.setattr(manager, '_check_repository', lambda: True)
    monkeypatch.setattr(manager, 'list_snapshots', lambda app_id: [{"id": "snap-1", "short_id": "snap-1"}])
    monkeypatch.setattr(manager, '_run_restic_container', lambda command, extra_volumes: '{"message_type":"summary"}')
    monkeypatch.setattr(manager, '_ensure_restored_app_running', lambda *args, **kwargs: None)
    monkeypatch.setattr(back_manager_module, 'AppManger', lambda: types.SimpleNamespace(
        get_app_by_id=lambda app_id: types.SimpleNamespace(
            endpointId=1,
            volumes=[{"Mountpoint": "/var/lib/docker/volumes/wordpress_demo/_data", "Name": "wordpress_demo"}],
        )
    ))
    monkeypatch.setattr(back_manager_module, 'PortainerManager', lambda: portainer)
    monkeypatch.setattr(manager, '_resolve_host_path', lambda path: path)

    manager.restore_backup('wordpress_demo', 'snap-1')

    assert portainer.start_calls == [('wordpress_demo', 1)]
    assert portainer.up_calls == []


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