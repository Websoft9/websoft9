import sys
from pathlib import Path
from typing import Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import files_agent


class FakeContainer:
    def __init__(self, container_id: str, *, labels: Optional[Dict[str, str]] = None, running: bool = True):
        self.id = container_id
        self.removed = False
        self.attrs = {
            "Config": {"Labels": labels or {}},
            "State": {"Running": running},
        }

    def reload(self):
        return None

    def remove(self, force: bool = False):
        self.removed = True
        self.attrs["State"]["Running"] = False


class FakeContainers:
    def __init__(self, containers: List[FakeContainer]):
        self._containers = containers

    def list(self, all: bool = False, filters: Optional[Dict[str, str]] = None):
        items = [container for container in self._containers if not container.removed]
        if not filters:
            return items
        label_filter = filters.get("label")
        if not label_filter:
            return items
        key, expected = label_filter.split("=", 1)
        return [
            container
            for container in items
            if (container.attrs.get("Config", {}).get("Labels", {}) or {}).get(key) == expected
        ]

    def get(self, container_ref: str):
        for container in self._containers:
            if container.id == container_ref and not container.removed:
                return container
        raise KeyError(container_ref)


class FakeDockerClient:
    def __init__(self, containers: List[FakeContainer]):
        self.containers = FakeContainers(containers)


def _clear_root_caches():
    files_agent._docker_allowed_roots.cache_clear()
    files_agent._allowed_roots.cache_clear()


def test_detect_docker_volumes_root_prefers_env_override(monkeypatch, tmp_path: Path):
    docker_volumes_root = tmp_path / "docker-root" / "volumes"
    docker_volumes_root.mkdir(parents=True)
    monkeypatch.setenv("WEBSOFT9_DOCKER_VOLUMES_ROOT", str(docker_volumes_root))

    detected = files_agent._detect_docker_volumes_root()

    assert detected == str(docker_volumes_root.resolve())


def test_should_use_helper_root_skips_helper_when_mounted_root_exists(monkeypatch, tmp_path: Path):
    docker_volumes_root = tmp_path / "docker-root" / "volumes"
    target_root = docker_volumes_root / "moodle_data" / "_data"
    target_root.mkdir(parents=True)
    monkeypatch.setenv("WEBSOFT9_DOCKER_VOLUMES_ROOT", str(docker_volumes_root))
    _clear_root_caches()

    try:
        assert files_agent._should_use_helper_root(str(target_root)) is False
    finally:
        _clear_root_caches()


def test_should_use_helper_root_falls_back_for_missing_path_under_allowed_root(monkeypatch, tmp_path: Path):
    docker_volumes_root = tmp_path / "docker-root" / "volumes"
    docker_volumes_root.mkdir(parents=True)
    missing_root = docker_volumes_root / "moodle_data" / "_data"
    monkeypatch.setenv("WEBSOFT9_DOCKER_VOLUMES_ROOT", str(docker_volumes_root))
    _clear_root_caches()

    try:
        assert files_agent._should_use_helper_root(str(missing_root)) is True
    finally:
        _clear_root_caches()


def test_helper_manager_prunes_orphaned_helpers_on_startup(monkeypatch):
    orphan = FakeContainer(
        "helper-1",
        labels={
            "com.websoft9.role": "files-helper",
            "com.websoft9.files-root": "/var/lib/docker/volumes/moodle_data/_data",
        },
    )
    docker_client = FakeDockerClient([orphan])
    monkeypatch.setattr(files_agent.DockerHelperManager, "_start_background_sweeper", lambda self: None)

    files_agent.DockerHelperManager(docker_client=docker_client)

    assert orphan.removed is True


def test_helper_manager_prunes_stale_tracked_helper(monkeypatch):
    helper = FakeContainer(
        "helper-2",
        labels={
            "com.websoft9.role": "files-helper",
            "com.websoft9.files-root": "/var/lib/docker/volumes/moodle_data/_data",
        },
    )
    docker_client = FakeDockerClient([helper])
    monkeypatch.setattr(files_agent.DockerHelperManager, "_start_background_sweeper", lambda self: None)
    manager = files_agent.DockerHelperManager(docker_client=docker_client, idle_ttl_seconds=30)
    manager._helpers = {
        "/var/lib/docker/volumes/moodle_data/_data": {
            "container_id": helper.id,
            "last_used": 0.0,
        }
    }
    monkeypatch.setattr(files_agent.time, "monotonic", lambda: 61.0)

    manager._prune_stale_locked()

    assert helper.removed is True
    assert manager._helpers == {}