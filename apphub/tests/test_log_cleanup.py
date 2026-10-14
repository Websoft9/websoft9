import fcntl
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.log_cleanup import LogCleanupService, LogTarget


def _service(tmp_path, pattern=r"service\.log", rotate=True):
    logs = tmp_path / "logs"
    logs.mkdir(exist_ok=True)
    return LogCleanupService(targets=[LogTarget(logs, pattern, rotate)], state_dir=tmp_path / "state", now=2_000_000_000, max_bytes=100)


def _old(path):
    path.write_text("old log\n")
    os.utime(path, (1_990_000_000, 1_990_000_000))


def test_cleanup_only_removes_expired_whitelisted_archives(tmp_path):
    service = _service(tmp_path)
    logs = tmp_path / "logs"
    for name in ("service.log.1", "service.log.2026-09-01.gz", "service.log", "database.sqlite", "credential.json", "service.log.backup", "other.log.1"):
        _old(logs / name)
    (logs / "service.log.2.gz").write_text("recent")
    os.utime(logs / "service.log.2.gz", (service.now, service.now))
    result = service.run()
    assert result["status"] == "success"
    assert result["deleted_files"] == 2
    assert result["freed_bytes"] == 16
    assert sorted(path.name for path in logs.iterdir()) == ["credential.json", "database.sqlite", "other.log.1", "service.log", "service.log.2.gz", "service.log.backup"]


def test_cleanup_skips_symlinks_hardlinks_and_directories(tmp_path):
    service = _service(tmp_path)
    outside = tmp_path / "outside"
    _old(outside)
    logs = tmp_path / "logs"
    (logs / "service.log.1").symlink_to(outside)
    os.link(outside, logs / "service.log.2")
    (logs / "service.log.3").mkdir()
    result = service.run()
    assert result["skipped_files"] == 3
    assert outside.read_text() == "old log\n"


def test_cleanup_skips_symlinked_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    _old(outside / "service.log.1")
    (tmp_path / "logs").symlink_to(outside, target_is_directory=True)
    service = LogCleanupService(targets=[LogTarget(tmp_path / "logs", r"service\.log")], state_dir=tmp_path / "state")
    assert service.run()["skipped_files"] == 1
    assert (outside / "service.log.1").exists()


def test_concurrent_cleanup_is_skipped(tmp_path):
    service = _service(tmp_path)
    service.state_dir.mkdir()
    with (service.state_dir / "cleanup.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert service.run()["status"] == "skipped"


def test_permission_error_is_reported_as_failure(tmp_path, monkeypatch):
    service = _service(tmp_path)
    events = []
    service.on_progress = events.append
    archive = tmp_path / "logs/service.log.1"
    _old(archive)
    original = Path.unlink

    def deny(path, *args, **kwargs):
        if path == archive:
            raise PermissionError("denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny)
    result = service.run()
    assert result["status"] == "failed"
    assert result["deleted_files"] == 0
    assert "PermissionError" in result["errors"][0]
    assert any(event["action"] == "failed" and event.get("reason") == "PermissionError" for event in events)
    assert events[-1]["status"] == "failed"


def test_active_rotation_preserves_inode_and_uses_private_config(tmp_path, monkeypatch):
    service = _service(tmp_path)
    active = tmp_path / "logs/service.log"
    active.write_text("x" * 200)
    inode = active.stat().st_ino

    def rotate(command, **kwargs):
        configuration = Path(command[-1]).read_text()
        assert "copytruncate" in configuration and "compress" in configuration
        assert "size 100" in configuration
        assert Path(command[-1]).stat().st_mode & 0o777 == 0o600
        active.write_text("")
        Path(str(active) + ".1.gz").write_bytes(b"compressed")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", rotate)
    result = service.run()
    assert result["status"] == "success"
    assert result["rotated_files"] == 1
    assert result["freed_bytes"] == 190
    assert active.stat().st_ino == inode


def test_existing_rotation_is_not_replaced(tmp_path, monkeypatch):
    service = _service(tmp_path, rotate=False)
    (tmp_path / "logs/service.log").write_text("x" * 200)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("must not rotate managed logs"))
    assert service.run()["rotated_files"] == 0


def test_failed_rotation_is_not_reported_as_success(tmp_path, monkeypatch):
    service = _service(tmp_path)
    (tmp_path / "logs/service.log").write_text("x" * 200)
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 1))
    result = service.run()
    assert result["status"] == "failed"
    assert result["rotated_files"] == 0


def test_default_scope_includes_configured_gitea_logs_without_touching_config(tmp_path, monkeypatch):
    from src.services.log_cleanup import _default_targets

    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("WEBSOFT9_SERVICE_LOG_ROOT", raising=False)
    config = tmp_path / "gitea/conf/app.ini"
    config.parent.mkdir(parents=True)
    config.write_text(f"WORK_PATH = /legacy\n[log]\nROOT_PATH = {tmp_path}/gitea-logs\n")
    original = config.read_bytes()
    assert any(target.directory == tmp_path / "gitea-logs" for target in _default_targets())
    assert config.read_bytes() == original


def test_rotation_timeout_reports_partial_failure(tmp_path, monkeypatch):
    service = _service(tmp_path)
    (tmp_path / "logs/service.log").write_text("x" * 200)

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 300)

    monkeypatch.setattr(subprocess, "run", timeout)
    result = service.run()
    assert result["status"] == "failed"
    assert "TimeoutExpired" in result["errors"][0]


@pytest.mark.parametrize("status,exit_code", [("success", 0), ("skipped", 75), ("failed", 1)])
def test_log_cleanup_cli_exit_codes(monkeypatch, status, exit_code):
    from click.testing import CliRunner
    from src.cli.apphub_cli import cli

    monkeypatch.setattr(LogCleanupService, "run", lambda self: {"status": status, "deleted_files": 0})
    result = CliRunner().invoke(cli, ["log-cleanup", "--json"])
    assert result.exit_code == exit_code
    assert f'"status": "{status}"' in result.output


def test_progress_reports_files_and_summary_without_log_contents(tmp_path):
    service = _service(tmp_path)
    events = []
    service.on_progress = events.append
    logs = tmp_path / "logs"
    _old(logs / "service.log.1")
    (logs / "service.log.2.gz").write_text("private archive contents")
    os.utime(logs / "service.log.2.gz", (service.now, service.now))
    (logs / "service.log").write_text("private active contents")
    (logs / "credential.json").write_text("unrelated secret")
    result = service.run()
    assert events[0]["action"] == "start"
    assert any(event["action"] == "scan" for event in events)
    files = {Path(event["path"]).name: event for event in events if event["action"] in {"deleted", "retained"}}
    assert files["service.log.1"]["reason"] == "archive_expired"
    assert files["service.log.2.gz"]["reason"] == "archive_within_retention"
    assert files["service.log"]["reason"] == "below_rotation_threshold"
    assert "private" not in str(events) and "unrelated secret" not in str(events)
    assert "credential.json" not in str(events)
    assert events[-1]["action"] == "summary"
    assert events[-1]["deleted_files"] == result["deleted_files"] == 1
    assert events[-1]["duration_seconds"] >= 0


def test_progress_reports_managed_logs_missing_directories_and_lock(tmp_path):
    service = _service(tmp_path, rotate=False)
    events = []
    service.on_progress = events.append
    (tmp_path / "logs/service.log").write_text("x" * 200)
    service.targets.append(LogTarget(tmp_path / "missing", r"service\.log"))
    service.run()
    assert any(event.get("reason") == "managed_by_service" for event in events)
    assert any(event.get("reason") == "directory_missing" for event in events)
    events.clear()
    with (service.state_dir / "cleanup.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert service.run()["status"] == "skipped"
    assert events[1]["reason"] == "previous_execution_running"
    assert events[-1]["status"] == "skipped"


@pytest.mark.parametrize("exit_code", [0, 1])
def test_progress_reports_rotation_result(tmp_path, monkeypatch, exit_code):
    service = _service(tmp_path)
    events = []
    service.on_progress = events.append
    active = tmp_path / "logs/service.log"
    active.write_text("x" * 200)

    def rotate(command, **kwargs):
        if exit_code == 0:
            active.write_text("")
            Path(str(active) + ".1.gz").write_bytes(b"compressed")
        return subprocess.CompletedProcess(command, exit_code)

    monkeypatch.setattr(subprocess, "run", rotate)
    service.run()
    assert any(event["action"] == "rotating" for event in events)
    final = next(event for event in events if event["action"] in {"rotated", "failed"})
    if exit_code == 0:
        assert final["freed_bytes"] == 190
        assert final["archive_path"] == str(active) + ".1.gz"
    else:
        assert final["reason"] == "logrotate_exit_1"
    assert events[-1]["status"] == ("success" if exit_code == 0 else "failed")


def test_cli_prints_structured_actions_without_debug_noise(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from src.cli.apphub_cli import cli

    service = _service(tmp_path)
    archive = tmp_path / "logs/service.log.1"
    _old(archive)
    (tmp_path / "logs/service.log").write_text("private log contents")

    def create_service(**kwargs):
        service.on_progress = kwargs["on_progress"]
        return service

    monkeypatch.setattr("src.services.log_cleanup.LogCleanupService", create_service)
    result = CliRunner().invoke(cli, ["log-cleanup"])
    assert result.exit_code == 0
    assert len(result.output.splitlines()) == 3
    assert "INFO event=start" in result.output
    assert "INFO event=deleted" in result.output
    assert "INFO event=summary" in result.output
    assert "examined_files=2" in result.output
    assert "retained_files=1" in result.output
    assert 'result="changes_applied"' in result.output
    assert "DEBUG" not in result.output and "private log contents" not in result.output
    assert str(archive) in result.output
    assert result.output.isascii()


@pytest.mark.parametrize("options", [[], ["--verbose"], ["--json"]])
def test_cli_no_changes_verbose_and_json_modes(tmp_path, monkeypatch, options):
    import json
    from click.testing import CliRunner
    from src.cli.apphub_cli import cli

    service = _service(tmp_path)
    active = tmp_path / "logs/service.log"
    active.write_text("private log contents")

    def create_service(**kwargs):
        service.on_progress = kwargs["on_progress"]
        return service

    monkeypatch.setattr("src.services.log_cleanup.LogCleanupService", create_service)
    result = CliRunner().invoke(cli, ["log-cleanup", *options])
    assert result.exit_code == 0
    assert "private log contents" not in result.output
    if "--json" in options:
        payload = json.loads(result.output)
        assert payload["result"] == "no_changes"
        assert payload["examined_files"] == payload["retained_files"] == 1
        assert len(result.output.splitlines()) == 1
    elif "--verbose" in options:
        assert "DEBUG event=scan" in result.output
        assert "DEBUG event=retained" in result.output
        assert str(active) in result.output
    else:
        assert len(result.output.splitlines()) == 2
        assert str(active) not in result.output
        assert 'result="no_changes"' in result.output


def test_insufficient_space_reports_reason_without_rotating(tmp_path, monkeypatch):
    import shutil

    service = _service(tmp_path)
    events = []
    service.on_progress = events.append
    active = tmp_path / "logs/service.log"
    active.write_text("x" * 200)
    monkeypatch.setattr(shutil, "disk_usage", lambda path: type("Usage", (), {"free": 0})())
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("must not rotate without space"))
    result = service.run()
    assert result["status"] == "failed"
    assert active.stat().st_size == 200
    assert any(event.get("reason") == "insufficient_disk_space" for event in events)