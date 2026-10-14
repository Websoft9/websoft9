from __future__ import annotations

import configparser
import errno
import fcntl
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


LOG_RETENTION_DAYS = 7
MAX_LOG_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class LogTarget:
    directory: Path
    pattern: str
    rotate_active: bool = True


def _default_targets() -> list[LogTarget]:
    data_root = Path(os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data"))
    service_root = Path(os.getenv("WEBSOFT9_SERVICE_LOG_ROOT", str(data_root / "logs")))
    apphub_root = Path(os.getenv("WEBSOFT9_LOG_DIR", "/websoft9/apphub/logs"))
    gitea_root = Path(os.getenv("WEBSOFT9_GITEA_DATA_DIR", str(data_root / "gitea")))
    gitea_logs = gitea_root / "log"
    config_path = gitea_root / "conf/app.ini"
    if config_path.is_file():
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read_string("[DEFAULT]\n" + config_path.read_text(encoding="utf-8"))
        gitea_logs = Path(config.get("log", "ROOT_PATH", fallback=str(gitea_logs)))
    return [
        LogTarget(apphub_root, r"apphub(?:_access|_error|_install)?\.log", False),
        LogTarget(service_root, r"(?:platform-gateway-(?:access|error)|platform-runtime|fallback_(?:access|error)|proxy-host-\d+_(?:access|error))\.log"),
        LogTarget(service_root / "gitea", r"service\.log"),
        LogTarget(gitea_logs, r"(?:gitea|router|access|xorm)\.log", False),
        LogTarget(service_root / "portainer", r"service\.log"),
        LogTarget(service_root / "npm", r"(?:backend|nginx)\.log"),
        LogTarget(Path("/var/log"), r"supervisord\.log", False),
    ]


class LogCleanupService:
    def __init__(self, *, targets: list[LogTarget] | None = None, state_dir: Path | None = None, now: float | None = None, max_bytes: int = MAX_LOG_BYTES, on_progress: Callable[[dict], None] | None = None):
        self.targets = targets
        data_root = Path(os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data"))
        self.state_dir = state_dir or data_root / "config/apphub/log-cleanup"
        self.now = now
        self.max_bytes = max_bytes
        self.on_progress = on_progress

    def _report(self, action: str, **details) -> None:
        if self.on_progress is not None:
            self.on_progress({"action": action, **details})

    def _finish(self, result: dict, started: float) -> dict:
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        result["result"] = result["status"] if result["status"] != "success" else ("changes_applied" if result["deleted_files"] or result["rotated_files"] else "no_changes")
        self._report("summary", **result)
        return result

    def _record_error(self, path: Path, exc: Exception, result: dict) -> None:
        result["errors"].append(f"{path}: {type(exc).__name__}")
        reason = type(exc).__name__
        if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            reason = "insufficient_disk_space"
        self._report("failed", path=str(path), reason=reason)

    def run(self) -> dict:
        started = time.monotonic()
        result = {"status": "success", "examined_files": 0, "retained_files": 0, "deleted_files": 0, "rotated_files": 0, "freed_bytes": 0, "skipped_files": 0, "errors": []}
        self._report("start", retention_days=LOG_RETENTION_DAYS, max_bytes=self.max_bytes)
        self.state_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.state_dir.is_symlink() or self.state_dir.resolve() != self.state_dir.absolute():
            raise OSError("Unsafe log cleanup state directory")
        self.state_dir.chmod(0o700)
        descriptor = os.open(self.state_dir / "cleanup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a") as lock:
            os.fchmod(lock.fileno(), 0o600)
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                result["status"] = "skipped"
                self._report("skipped", path=str(self.state_dir / "cleanup.lock"), reason="previous_execution_running")
                return self._finish(result, started)
            cutoff = (time.time() if self.now is None else self.now) - LOG_RETENTION_DAYS * 86400
            seen = set()
            for target in self.targets if self.targets is not None else _default_targets():
                try:
                    self._clean_target(target, cutoff, seen, result)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    self._record_error(target.directory, exc, result)
            if result["errors"]:
                result["status"] = "failed"
        return self._finish(result, started)

    def _clean_target(self, target: LogTarget, cutoff: float, seen: set, result: dict) -> None:
        directory = target.directory
        self._report("scan", path=str(directory), pattern=target.pattern, rotate_active=target.rotate_active)
        if not directory.exists():
            self._report("skipped", path=str(directory), reason="directory_missing")
            return
        if directory.is_symlink() or directory.resolve() != directory.absolute():
            result["skipped_files"] += 1
            self._report("skipped", path=str(directory), reason="unsafe_directory")
            return
        pattern = re.compile(rf"(?P<base>{target.pattern})(?P<archive>\.(?:\d+|\d{{4}}-\d{{2}}-\d{{2}})(?:\.gz)?)?")
        for path in directory.iterdir():
            match = pattern.fullmatch(path.name)
            if match is None or path in seen:
                continue
            seen.add(path)
            result["examined_files"] += 1
            try:
                metadata = path.lstat()
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    result["skipped_files"] += 1
                    self._report("skipped", path=str(path), reason="non_regular_or_linked_file")
                    continue
                if match.group("archive"):
                    if metadata.st_mtime < cutoff:
                        path.unlink()
                        result["deleted_files"] += 1
                        result["freed_bytes"] += metadata.st_size
                        self._report("deleted", path=str(path), size_bytes=metadata.st_size, reason="archive_expired")
                    else:
                        result["retained_files"] += 1
                        self._report("retained", path=str(path), size_bytes=metadata.st_size, reason="archive_within_retention")
                elif target.rotate_active and metadata.st_size > self.max_bytes:
                    self._rotate(path, metadata, result)
                else:
                    result["retained_files"] += 1
                    reason = "managed_by_service" if not target.rotate_active else "below_rotation_threshold"
                    self._report("retained", path=str(path), size_bytes=metadata.st_size, reason=reason)
            except FileNotFoundError:
                result["skipped_files"] += 1
                self._report("skipped", path=str(path), reason="file_disappeared")
            except (OSError, subprocess.TimeoutExpired) as exc:
                self._record_error(path, exc, result)

    def _rotate(self, path: Path, metadata: os.stat_result, result: dict) -> None:
        if any(character in str(path) for character in "\r\n\x00"):
            raise OSError("Invalid log path")
        if shutil.disk_usage(path.parent).free < metadata.st_size * 2:
            raise OSError(errno.ENOSPC, "Insufficient space for safe log rotation")
        self._report("rotating", path=str(path), size_bytes=metadata.st_size)
        escaped_path = str(path).replace("\\", "\\\\").replace('"', '\\"')
        configuration = (
            f'"{escaped_path}" {{\n'
            f"    size {self.max_bytes}\n"
            "    rotate 7\n"
            "    missingok\n"
            "    notifempty\n"
            "    compress\n"
            "    copytruncate\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.state_dir) as config:
            config.write(configuration)
            config.flush()
            process = subprocess.run(
                ["logrotate", "--state", str(self.state_dir / "logrotate.state"), config.name],
                capture_output=True, text=True, timeout=300, check=False,
            )
        if process.returncode != 0:
            result["errors"].append(f"{path}: logrotate exited with code {process.returncode}")
            self._report("failed", path=str(path), reason=f"logrotate_exit_{process.returncode}")
            return
        after = path.stat()
        if after.st_ino != metadata.st_ino or after.st_dev != metadata.st_dev:
            result["errors"].append(f"{path}: active log changed during rotation")
            self._report("failed", path=str(path), reason="active_log_changed")
            return
        result["rotated_files"] += 1
        reclaimed = max(0, metadata.st_size - after.st_size)
        archive = Path(str(path) + ".1.gz")
        if archive.is_file():
            reclaimed = max(0, reclaimed - archive.stat().st_size)
        result["freed_bytes"] += reclaimed
        self._report("rotated", path=str(path), archive_path=str(archive), size_bytes=metadata.st_size, after_bytes=after.st_size, freed_bytes=reclaimed)