import json
import threading
import time
from datetime import datetime, timedelta, timezone

from src.services.release_checker import (
    BACKGROUND_TIMEOUT_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    ReleaseVersionChecker,
)


def _iso(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")


def _checker(tmp_path) -> ReleaseVersionChecker:
    return ReleaseVersionChecker(data_root=str(tmp_path / "data"))


def _stub_remote(monkeypatch, checker, *, version="2.4.2", error=None):
    calls = []

    def fake_fetch(channel, *, timeout):
        calls.append({"channel": channel, "timeout": timeout})
        if error is not None:
            raise error
        return version

    monkeypatch.setattr(checker, "fetch_remote_version", fake_fetch)
    return calls


def test_missing_cache_triggers_a_check_and_caches_the_result(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    calls = _stub_remote(monkeypatch, checker, version="2.4.2")

    assert checker.ensure_latest_version(channel="dev") == "2.4.2"
    assert calls == [{"channel": "dev", "timeout": BACKGROUND_TIMEOUT_SECONDS}]

    cache = json.loads(checker.cache_file.read_text(encoding="utf-8"))
    assert cache["channel"] == "dev"
    assert cache["version"] == "2.4.2"
    assert cache["checked_at"]
    assert cache["last_error"] is None


def test_fresh_cache_is_served_without_any_network_call(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    checker._write_cache({
        "channel": "dev",
        "version": "2.4.2",
        "checked_at": _iso(1),
        "last_attempt_at": _iso(1),
        "last_error": None,
    })
    calls = _stub_remote(monkeypatch, checker, error=RuntimeError("network must not be used"))

    assert checker.ensure_latest_version(channel="dev") == "2.4.2"
    assert calls == []


def test_stale_cache_is_refreshed(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    checker._write_cache({
        "channel": "dev",
        "version": "2.4.2",
        "checked_at": _iso(30),
        "last_attempt_at": _iso(30),
        "last_error": None,
    })
    calls = _stub_remote(monkeypatch, checker, version="2.4.3")

    assert checker.ensure_latest_version(channel="dev") == "2.4.3"
    assert len(calls) == 1


def test_cache_from_another_channel_is_ignored(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    checker._write_cache({
        "channel": "dev",
        "version": "2.4.2",
        "checked_at": _iso(1),
        "last_attempt_at": _iso(1),
        "last_error": None,
    })
    calls = _stub_remote(monkeypatch, checker, version="2.4.0")

    assert checker.ensure_latest_version(channel="release") == "2.4.0"
    assert calls == [{"channel": "release", "timeout": BACKGROUND_TIMEOUT_SECONDS}]


def test_failed_check_keeps_the_previous_version_and_throttles_the_next_call(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    previous_checked_at = _iso(30)
    checker._write_cache({
        "channel": "dev",
        "version": "2.4.2",
        "checked_at": previous_checked_at,
        "last_attempt_at": previous_checked_at,
        "last_error": None,
    })
    calls = _stub_remote(monkeypatch, checker, error=RuntimeError("artifact server unreachable"))

    # A transient failure must not look like "this platform is already up to date".
    assert checker.ensure_latest_version(channel="dev") == "2.4.2"
    assert len(calls) == 1

    cache = json.loads(checker.cache_file.read_text(encoding="utf-8"))
    assert cache["version"] == "2.4.2"
    assert cache["checked_at"] == previous_checked_at
    assert "unreachable" in cache["last_error"]

    # The failed attempt is throttled, so the next caller does not retry the network.
    assert checker.ensure_latest_version(channel="dev") == "2.4.2"
    assert len(calls) == 1


def test_failure_without_a_previous_cache_returns_none(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    _stub_remote(monkeypatch, checker, error=RuntimeError("artifact server unreachable"))

    assert checker.ensure_latest_version(channel="dev") is None


def test_force_refreshes_even_when_the_cache_is_fresh(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    checker._write_cache({
        "channel": "dev",
        "version": "2.4.2",
        "checked_at": _iso(1),
        "last_attempt_at": _iso(1),
        "last_error": None,
    })
    calls = _stub_remote(monkeypatch, checker, version="2.4.3")

    assert checker.ensure_latest_version(channel="dev", force=True) == "2.4.3"
    assert len(calls) == 1


def test_request_scoped_call_uses_the_short_timeout(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    calls = _stub_remote(monkeypatch, checker)

    checker.ensure_latest_version(channel="dev", background=False)

    assert calls == [{"channel": "dev", "timeout": REQUEST_TIMEOUT_SECONDS}]


def test_success_clears_a_previous_error(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    checker._write_cache({
        "channel": "dev",
        "version": "2.4.2",
        "checked_at": _iso(30),
        "last_attempt_at": _iso(30),
        "last_error": "artifact server unreachable",
    })
    _stub_remote(monkeypatch, checker, version="2.4.2")

    checker.ensure_latest_version(channel="dev")

    cache = json.loads(checker.cache_file.read_text(encoding="utf-8"))
    assert cache["last_error"] is None


def test_request_path_answers_from_cache_instead_of_waiting_for_a_refresh(tmp_path, monkeypatch):
    checker = _checker(tmp_path)
    checker._write_cache({
        "channel": "dev",
        "version": "2.4.2",
        "checked_at": _iso(30),
        "last_attempt_at": _iso(30),
        "last_error": None,
    })
    started = threading.Event()
    release = threading.Event()

    def slow_fetch(channel, *, timeout):
        started.set()
        release.wait(10)
        return "2.4.3"

    monkeypatch.setattr(checker, "fetch_remote_version", slow_fetch)
    worker = threading.Thread(target=lambda: checker.ensure_latest_version(channel="dev", force=True), daemon=True)
    worker.start()
    assert started.wait(5)

    began = time.monotonic()
    value = checker.ensure_latest_version(channel="dev", background=False)
    elapsed = time.monotonic() - began

    release.set()
    worker.join(5)

    assert value == "2.4.2"
    assert elapsed < 1
