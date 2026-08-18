from __future__ import annotations

from pathlib import Path
import sqlite3

from src.services.platform_readiness import PlatformReadinessService


def _write_sqlite(database_file: Path, table_name: str) -> None:
    database_file.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_file))
    try:
        connection.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()


def test_ready_when_all_checks_pass(monkeypatch, tmp_path):
    data_root = tmp_path / "data"
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(data_root))
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(data_root / "config" / "product-auth"))
    monkeypatch.setenv("WEBSOFT9_INSTALL_TRACKING_DIR", str(data_root / "config" / "apphub"))
    monkeypatch.setenv("WEBSOFT9_HOST_ACCESS_DATA_DIR", str(data_root / "config" / "host-access"))

    _write_sqlite(data_root / "config" / "product-auth" / "product-auth.sqlite", "operators")
    _write_sqlite(data_root / "config" / "apphub" / "install-tracking.sqlite", "install_tasks")
    _write_sqlite(data_root / "config" / "host-access" / "host-access.sqlite", "host_profiles")

    for relative_path in (
        "gitea/credential",
        "portainer/credential",
        "credential.json",
        "custom_ssl/websoft9-self-signed.cert",
    ):
        marker = data_root / relative_path
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("ok", encoding="utf-8")

    service = PlatformReadinessService(http_probe=lambda url: True)

    ready, pending = service.check()

    assert ready is True
    assert pending == []


def test_pending_lists_sqlite_and_service_failures(monkeypatch, tmp_path):
    data_root = tmp_path / "data"
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(data_root))

    service = PlatformReadinessService(http_probe=lambda url: False)

    ready, pending = service.check()

    assert ready is False
    assert "product-auth" in pending
    assert "install-tracking" in pending
    assert "host-access" in pending
    assert "gitea" in pending
    assert "portainer" in pending
    assert "nginx-proxy-manager" in pending


def test_missing_markers_are_reported(monkeypatch, tmp_path):
    data_root = tmp_path / "data"
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(data_root))
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(data_root / "config" / "product-auth"))
    monkeypatch.setenv("WEBSOFT9_INSTALL_TRACKING_DIR", str(data_root / "config" / "apphub"))
    monkeypatch.setenv("WEBSOFT9_HOST_ACCESS_DATA_DIR", str(data_root / "config" / "host-access"))

    _write_sqlite(data_root / "config" / "product-auth" / "product-auth.sqlite", "operators")
    _write_sqlite(data_root / "config" / "apphub" / "install-tracking.sqlite", "install_tasks")
    _write_sqlite(data_root / "config" / "host-access" / "host-access.sqlite", "host_profiles")

    service = PlatformReadinessService(http_probe=lambda url: True)

    ready, pending = service.check()

    assert ready is False
    assert "gitea-credential" in pending
    assert "portainer-credential" in pending
    assert "npm-credential" in pending
    assert "npm-certificate" in pending


def test_sqlite_missing_table_reports_pending(monkeypatch, tmp_path):
    data_root = tmp_path / "data"
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(data_root))
    monkeypatch.setenv("WEBSOFT9_PRODUCT_AUTH_DATA_DIR", str(data_root / "config" / "product-auth"))
    monkeypatch.setenv("WEBSOFT9_INSTALL_TRACKING_DIR", str(data_root / "config" / "apphub"))
    monkeypatch.setenv("WEBSOFT9_HOST_ACCESS_DATA_DIR", str(data_root / "config" / "host-access"))

    database_file = data_root / "config" / "product-auth" / "product-auth.sqlite"
    database_file.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_file))
    connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    service = PlatformReadinessService(http_probe=lambda url: True)

    ready, pending = service.check()

    assert ready is False
    assert "product-auth" in pending
