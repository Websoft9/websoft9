import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Importing the app modules initialises the install-tracking store; keep it away from the
# host's real data root so a test run can never touch a live deployment.
os.environ.setdefault("WEBSOFT9_INSTALL_TRACKING_DIR", tempfile.mkdtemp(prefix="w9-tracking-"))

from src.core.exception import CustomException
from src.services import upgrade_manager
from src.services.upgrade_manager import UpgradeManager


def test_checksums_reject_duplicate_artifact_name():
    digest = "a" * 64

    with pytest.raises(CustomException, match="Duplicate checksum entry"):
        UpgradeManager._checksums(f"{digest} runner-upgrade.sh\n{digest} runner-upgrade.sh\n")


def test_auto_download_defaults_to_on(monkeypatch):
    class MissingSection:
        def get_value(self, section, key):
            raise KeyError(f"{section}/{key}")

    monkeypatch.setattr(upgrade_manager, "ConfigManager", lambda *args, **kwargs: MissingSection())

    assert upgrade_manager.auto_download_enabled() is True


def test_auto_download_can_be_disabled(monkeypatch):
    class Disabled:
        def get_value(self, section, key):
            assert (section, key) == ("upgrade", "auto_download")
            return "false"

    monkeypatch.setattr(upgrade_manager, "ConfigManager", lambda *args, **kwargs: Disabled())

    assert upgrade_manager.auto_download_enabled() is False


def test_auto_download_starts_a_prepare_for_a_newer_release(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(upgrade_manager, "auto_download_enabled", lambda: True)
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")
    starts = []
    monkeypatch.setattr(upgrade_manager.UpgradeManager, "start_prepare", lambda self: starts.append(self) or {})

    assert upgrade_manager.maybe_start_auto_download(latest_version="2.4.3") is True
    assert len(starts) == 1


def test_auto_download_ignores_missing_or_older_releases(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(upgrade_manager, "auto_download_enabled", lambda: True)
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")
    starts = []
    monkeypatch.setattr(upgrade_manager.UpgradeManager, "start_prepare", lambda self: starts.append(self) or {})

    assert upgrade_manager.maybe_start_auto_download(latest_version=None) is False
    assert upgrade_manager.maybe_start_auto_download(latest_version="2.4.2") is False
    assert upgrade_manager.maybe_start_auto_download(latest_version="2.4.1") is False
    assert starts == []


def test_auto_download_skips_a_release_that_is_already_staged(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    data_root = tmp_path / "data"
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(data_root))
    monkeypatch.setattr(upgrade_manager, "auto_download_enabled", lambda: True)
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")
    UpgradeManager(data_root=str(data_root))._write_state({"run_id": "run-1", "state": "ready", "target_version": "2.4.3"})
    starts = []
    monkeypatch.setattr(upgrade_manager.UpgradeManager, "start_prepare", lambda self: starts.append(self) or {})

    assert upgrade_manager.maybe_start_auto_download(latest_version="2.4.3") is False
    assert starts == []


def test_auto_download_skips_a_running_job(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    data_root = tmp_path / "data"
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(data_root))
    monkeypatch.setattr(upgrade_manager, "auto_download_enabled", lambda: True)
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")
    # Without a live runner the stale `applying` is healed into `apply_interrupted`, which is
    # deliberately retryable; keep the runner alive so the job counts as in progress.
    monkeypatch.setattr(upgrade_manager.UpgradeManager, "_runner_is_active", lambda self, run_id: True)
    UpgradeManager(data_root=str(data_root))._write_state({"run_id": "run-1", "state": "applying", "target_version": "2.4.3"})
    starts = []
    monkeypatch.setattr(upgrade_manager.UpgradeManager, "start_prepare", lambda self: starts.append(self) or {})

    assert upgrade_manager.maybe_start_auto_download(latest_version="2.4.3") is False
    assert starts == []


def test_auto_download_never_raises_when_the_prepare_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(upgrade_manager, "auto_download_enabled", lambda: True)
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")

    def failing_start(self):
        raise CustomException(409, "Upgrade In Progress", "another job already owns the lock")

    monkeypatch.setattr(upgrade_manager.UpgradeManager, "start_prepare", failing_start)

    assert upgrade_manager.maybe_start_auto_download(latest_version="2.4.3") is False


def test_auto_download_is_skipped_inside_test_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_auto_download_is_skipped_inside_test_runs")
    monkeypatch.setattr(upgrade_manager, "auto_download_enabled", lambda: True)
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")
    starts = []
    monkeypatch.setattr(upgrade_manager.UpgradeManager, "start_prepare", lambda self: starts.append(self) or {})

    assert upgrade_manager.maybe_start_auto_download(latest_version="2.4.3") is False
    assert starts == []


def test_compose_file_follows_the_file_the_deployment_used():
    manager = UpgradeManager(data_root="/tmp/websoft9-test-data")
    fallback = "/opt/websoft9/dev/docker-compose.yml"

    assert manager._resolve_compose_file({}, "/opt/websoft9/dev") == fallback
    assert manager._resolve_compose_file({"com.docker.compose.project.config_files": "docker-compose.yml"}, "/opt/websoft9/dev") == fallback
    # The runner only mounts the install path, so a file elsewhere is not usable.
    assert manager._resolve_compose_file({"com.docker.compose.project.config_files": "/etc/other/docker-compose.yml"}, "/opt/websoft9/dev") == fallback
    assert manager._resolve_compose_file(
        {"com.docker.compose.project.config_files": "/etc/other/extra.yml,/opt/websoft9/dev/docker-compose.dev.yml"},
        "/opt/websoft9/dev",
    ) == "/opt/websoft9/dev/docker-compose.dev.yml"


def test_prepare_writes_verified_task_with_precise_image_digest(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    install_path = tmp_path / "install"
    install_path.mkdir()
    (install_path / ".env").write_text("IMAGE_REPO=websoft9dev/websoft9\nIMAGE_TAG=2.4\n", encoding="utf-8")
    (install_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    manager = UpgradeManager(data_root=str(data_root), artifact_base_url="https://artifacts.example.test")

    manifest = {
        "image": {"repository": "websoft9dev/websoft9", "version_tag": "2.5.0"},
        "install": {"runner_upgrade_script": "runner-upgrade.sh"},
    }
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")
    monkeypatch.setattr(upgrade_manager, "read_release_channel", lambda: "release")
    monkeypatch.setattr(
        manager,
        "_download_and_verify_artifacts",
        lambda **_kwargs: (manifest, {"version": "2.5.0"}),
    )
    monkeypatch.setattr(
        manager,
        "_discover_deployment",
        lambda: {
            "install_path": str(install_path),
            "compose_project": "websoft9",
            "container_name": "websoft9",
            "compose_file": str(install_path / "docker-compose.yml"),
            "data_root": str(data_root),
        },
    )

    class Image:
        id = "sha256:" + "c" * 64
        attrs = {"RepoDigests": ["websoft9dev/websoft9@sha256:" + "b" * 64]}

    class Images:
        def pull(self, image_name):
            assert image_name in {"websoft9dev/websoft9:2.5.0", upgrade_manager.RUNNER_IMAGE}
            return Image()

    class Api:
        tags: list = []

        def tag(self, image, repository, tag=None, force=False):
            self.tags.append((image, repository, tag))

    class DockerClient:
        images = Images()
        api = Api()

    monkeypatch.setattr(upgrade_manager.docker, "from_env", lambda: DockerClient())

    status = manager.prepare()

    assert status["state"] == "ready"
    assert status["target_version"] == "2.5.0"
    task = (data_root / "upgrade" / "staging" / status["run_id"] / "task.env").read_text(encoding="utf-8")
    assert "TARGET_IMAGE_TAG=2.5.0\n" in task
    assert f"TARGET_IMAGE_DIGEST=sha256:{'b' * 64}\n" in task
    assert "INSTALL_PATH=" + str(install_path) in task
    assert "COMPOSE_FILE=" + str(install_path / "docker-compose.yml") + "\n" in task


def test_prepare_rejects_non_newer_target_before_inspecting_deployment(tmp_path, monkeypatch):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    monkeypatch.setattr(upgrade_manager, "read_release_version", lambda: "2.4.2")
    monkeypatch.setattr(upgrade_manager, "read_release_channel", lambda: "release")
    monkeypatch.setattr(
        manager,
        "_download_and_verify_artifacts",
        lambda **_kwargs: (
            {"image": {"repository": "websoft9dev/websoft9", "version_tag": "2.4.2"}, "install": {"runner_upgrade_script": "runner-upgrade.sh"}},
            {"version": "2.4.2"},
        ),
    )
    monkeypatch.setattr(manager, "_discover_deployment", lambda: pytest.fail("deployment inspection must not run"))

    with pytest.raises(CustomException, match="not newer"):
        manager.prepare()


def test_apply_starts_only_the_fixed_runner_for_a_ready_task(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_dir = data_root / "upgrade" / "staging" / "run-1"
    install_path = tmp_path / "install"
    staging_dir.mkdir(parents=True)
    install_path.mkdir()
    manager = UpgradeManager(data_root=str(data_root))
    (staging_dir / "task.env").write_text(
        "\n".join([
            "RUN_ID=run-1",
            f"DATA_ROOT={data_root}",
            f"STAGING_DIR={staging_dir}",
            f"INSTALL_PATH={install_path}",
            f"COMPOSE_FILE={install_path}/docker-compose.yml",
            "COMPOSE_PROJECT=websoft9",
            "TARGET_IMAGE_REPO=websoft9dev/websoft9",
            "TARGET_IMAGE_TAG=2.5.0",
            f"TARGET_IMAGE_DIGEST=sha256:{'b' * 64}",
            "TARGET_VERSION=2.5.0",
            "CONTAINER_NAME=websoft9",
            "",
        ]),
        encoding="utf-8",
    )
    manager._write_state({"run_id": "run-1", "state": "ready", "target_version": "2.5.0"})
    calls = []

    class Image:
        attrs = {"RepoDigests": [f"mirror.example.test/library/docker@{upgrade_manager.RUNNER_IMAGE_DIGEST}"]}

    class Images:
        def get(self, image_name):
            # Resolved through the tag: a mirror pull records its own repository for the digest.
            assert image_name == upgrade_manager.RUNNER_IMAGE_TAG
            return Image()

    class Containers:
        def run(self, **kwargs):
            calls.append(kwargs)

    class DockerClient:
        images = Images()
        containers = Containers()

    monkeypatch.setattr(upgrade_manager.docker, "from_env", lambda: DockerClient())

    status = manager.apply()

    assert status["state"] == "applying"
    assert len(calls) == 1
    assert calls[0]["image"] == upgrade_manager.RUNNER_IMAGE_TAG
    assert calls[0]["command"] == ["sh", f"{staging_dir}/runner-upgrade.sh", str(staging_dir / "task.env")]
    assert calls[0]["volumes"]["/var/run/docker.sock"] == {"bind": "/var/run/docker.sock", "mode": "rw"}


def test_apply_rejects_a_runner_image_that_lost_its_pin(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    staging_dir = data_root / "upgrade" / "staging" / "run-1"
    install_path = tmp_path / "install"
    staging_dir.mkdir(parents=True)
    install_path.mkdir()
    manager = UpgradeManager(data_root=str(data_root))
    (staging_dir / "task.env").write_text(
        "\n".join([
            "RUN_ID=run-1",
            f"DATA_ROOT={data_root}",
            f"STAGING_DIR={staging_dir}",
            f"INSTALL_PATH={install_path}",
            f"COMPOSE_FILE={install_path}/docker-compose.yml",
            "COMPOSE_PROJECT=websoft9",
            "TARGET_IMAGE_REPO=websoft9dev/websoft9",
            "TARGET_IMAGE_TAG=2.5.0",
            f"TARGET_IMAGE_DIGEST=sha256:{'b' * 64}",
            "TARGET_VERSION=2.5.0",
            "CONTAINER_NAME=websoft9",
            "",
        ]),
        encoding="utf-8",
    )
    manager._write_state({"run_id": "run-1", "state": "ready", "target_version": "2.5.0"})

    class Image:
        attrs = {"RepoDigests": ["docker@sha256:" + "0" * 64]}

    class Images:
        def get(self, image_name):
            return Image()

    class DockerClient:
        images = Images()
        containers = object()

    monkeypatch.setattr(upgrade_manager.docker, "from_env", lambda: DockerClient())

    with pytest.raises(CustomException, match="Upgrade Runner Unavailable"):
        manager.apply()


def test_apply_rejects_a_tampered_task_before_starting_runner(tmp_path):
    data_root = tmp_path / "data"
    staging_dir = data_root / "upgrade" / "staging" / "run-1"
    staging_dir.mkdir(parents=True)
    manager = UpgradeManager(data_root=str(data_root))
    (staging_dir / "task.env").write_text("RUN_ID=run-1\nUNKNOWN=value\n", encoding="utf-8")
    manager._write_state({"run_id": "run-1", "state": "ready"})

    with pytest.raises(CustomException, match="prepared task is invalid"):
        manager.apply()


def test_start_prepare_returns_downloading_and_runs_in_background(tmp_path, monkeypatch):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    started = threading.Event()
    release = threading.Event()

    def blocking_prepare(_run_id):
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(manager, "_prepare_locked", blocking_prepare)

    try:
        status = manager.start_prepare()

        assert status["state"] == "downloading"
        assert status["run_id"]
        assert started.wait(timeout=5)
    finally:
        release.set()
        for _ in range(50):
            if not manager._job_running():
                break
            time.sleep(0.05)


def test_start_prepare_rejects_while_another_job_holds_the_lock(tmp_path):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    held = manager._acquire_lock()
    try:
        with pytest.raises(CustomException, match="already active"):
            manager.start_prepare()
    finally:
        manager._release_lock(held)


def test_status_reports_an_interrupted_download_as_a_failure_record(tmp_path):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    manager._write_state({"run_id": "run-1", "state": "downloading"})

    status = manager.status()

    # The platform itself is idle again: the failure is a diagnostic, not a lifecycle state.
    assert status["state"] == "idle"
    assert status["detail"] is None
    assert status["last_failure"]["run_id"] == "run-1"
    assert status["last_failure"]["detail"] == "download_interrupted"


def test_status_keeps_downloading_while_the_job_is_running(tmp_path):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    held = manager._acquire_lock()
    try:
        manager._write_state({"run_id": "run-1", "state": "downloading"})
        assert manager.status()["state"] == "downloading"
    finally:
        manager._release_lock(held)


def test_stale_applying_run_is_reported_as_interrupted(tmp_path, monkeypatch):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    manager._write_state({"run_id": "run-1", "state": "applying", "detail": "runner started"})
    monkeypatch.setattr(manager, "_runner_is_active", lambda _run_id: False)

    status = manager.status()

    # The runner is gone, so the console must not stay pinned on "applying".
    assert status["state"] == "apply_interrupted"


def test_applying_stays_while_the_runner_is_alive(tmp_path, monkeypatch):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    manager._write_state({"run_id": "run-1", "state": "applying", "detail": "runner started"})
    monkeypatch.setattr(manager, "_runner_is_active", lambda _run_id: True)

    assert manager.status()["state"] == "applying"


def test_applying_falls_back_to_the_deadline_when_docker_is_unavailable(tmp_path, monkeypatch):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    monkeypatch.setattr(manager, "_runner_is_active", lambda _run_id: None)

    manager._write_state({"run_id": "run-1", "state": "applying"})
    assert manager.status()["state"] == "applying"

    manager.state_file.write_text(
        json.dumps({"run_id": "run-1", "state": "applying", "updated_at": "2020-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    assert manager.status()["state"] == "apply_interrupted"


def test_stale_applying_does_not_block_a_new_download(tmp_path, monkeypatch):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    manager._write_state({"run_id": "run-1", "state": "applying"})
    monkeypatch.setattr(manager, "_runner_is_active", lambda _run_id: False)

    release = threading.Event()

    def holding_prepare(_run_id):
        release.wait(timeout=5)

    monkeypatch.setattr(manager, "_prepare_locked", holding_prepare)
    try:
        status = manager.start_prepare()

        assert status["state"] == "downloading"
        assert status["run_id"] != "run-1"
    finally:
        release.set()
        for _ in range(50):
            if not manager._job_running():
                break
            time.sleep(0.05)


def test_live_applying_still_blocks_a_new_download(tmp_path, monkeypatch):
    manager = UpgradeManager(data_root=str(tmp_path / "data"))
    manager._write_state({"run_id": "run-1", "state": "applying"})
    monkeypatch.setattr(manager, "_runner_is_active", lambda _run_id: True)

    with pytest.raises(CustomException, match="already running"):
        manager.start_prepare()


def test_run_prepare_records_download_failure_and_releases_the_lock(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    manager = UpgradeManager(data_root=str(data_root))

    def failing_prepare(_run_id):
        raise CustomException(502, "Invalid Upgrade Artifact", "SHA256SUMS does not cover runner-upgrade.sh")

    monkeypatch.setattr(manager, "_prepare_locked", failing_prepare)
    manager._write_state({"run_id": "run-1", "state": "downloading"})
    lock = manager._acquire_lock()

    manager._run_prepare("run-1", lock)

    state = json.loads((data_root / "upgrade" / "state.json").read_text(encoding="utf-8"))
    assert state["state"] == "download_failed"
    assert "runner-upgrade.sh" in state["detail"]
    assert not manager._job_running()

    # The durable record survives on disk, but the reported lifecycle state is idle.
    status = manager.status()
    assert status["state"] == "idle"
    assert "runner-upgrade.sh" in status["last_failure"]["detail"]