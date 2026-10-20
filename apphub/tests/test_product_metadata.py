import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import product_metadata as product_metadata_service
from src.services import product_runtime_state as runtime_state_service


def _configure_runtime_state_paths(tmp_path, monkeypatch, *, version='2.3.0'):
    version_path = tmp_path / 'version.json'
    version_path.write_text(
        json.dumps({
            'version': version,
            'edition_key': 'free',
        }),
        encoding='utf-8',
    )
    monkeypatch.setattr(runtime_state_service, 'VERSION_FILE', version_path)
    monkeypatch.setenv('WEBSOFT9_INSTALL_TRACKING_DIR', str(tmp_path / 'apphub-data'))


def test_read_product_edition_discards_explicit_max_apps_from_metadata(tmp_path, monkeypatch):
    _configure_runtime_state_paths(tmp_path, monkeypatch)
    store = runtime_state_service.ProductRuntimeStateStore()
    store.write_runtime_state(
        edition_key='starter',
        max_apps=6,
        state_source='manual-support',
        updated_by='test',
    )

    edition = product_metadata_service.read_product_edition()

    assert edition.key == 'starter'
    assert edition.max_apps is None


def test_read_product_edition_has_no_catalog_app_limit(tmp_path, monkeypatch):
    _configure_runtime_state_paths(tmp_path, monkeypatch)
    store = runtime_state_service.ProductRuntimeStateStore()
    store.write_runtime_state(
        edition_key='standard',
        max_apps=None,
        state_source='manual-support',
        updated_by='test',
    )

    edition = product_metadata_service.read_product_edition()

    assert edition.key == 'standard'
    assert edition.max_apps is None


def test_write_product_edition_updates_metadata_file(tmp_path, monkeypatch):
    _configure_runtime_state_paths(tmp_path, monkeypatch, version='3.0.0')

    edition = product_metadata_service.write_product_edition('starter')
    payload = product_metadata_service.read_product_metadata()

    assert edition.key == 'starter'
    assert edition.max_apps is None
    assert payload['edition_key'] == 'starter'
    assert payload['max_apps'] is None
    assert payload['version'] == '3.0.0'


@pytest.mark.parametrize(
    ('legacy_max_apps', 'edition_key'),
    [
        (2, 'free'),
        (3, 'starter'),
        (5, 'standard'),
        (10, 'standard'),
        (10000, 'enterprise'),
    ],
)
def test_migrate_product_metadata_from_legacy_system_ini(tmp_path, monkeypatch, legacy_max_apps, edition_key):
    _configure_runtime_state_paths(tmp_path, monkeypatch, version='3.0.0')
    legacy_ini_path = tmp_path / 'system.ini'
    legacy_ini_path.write_text(f'[max_apps]\nkey = {legacy_max_apps}\n', encoding='utf-8')

    edition = product_metadata_service.migrate_product_metadata(
        version='3.0.0',
        legacy_system_ini_file=str(legacy_ini_path),
    )
    payload = product_metadata_service.read_product_metadata()

    assert edition.key == edition_key
    assert edition.max_apps is None
    assert payload['version'] == '3.0.0'
    assert payload['edition_key'] == edition_key
    assert payload['max_apps'] is None


def test_migrate_product_metadata_clears_existing_app_limit(tmp_path, monkeypatch):
    _configure_runtime_state_paths(tmp_path, monkeypatch, version='3.0.0')
    store = runtime_state_service.ProductRuntimeStateStore()
    store.write_runtime_state(
        edition_key='free',
        max_apps=2,
        state_source='install',
        updated_by='test',
    )

    edition = product_metadata_service.migrate_product_metadata(version='3.0.0')

    assert edition.key == 'free'
    assert edition.max_apps is None
    assert store.get_runtime_state_row()['max_apps'] is None


def test_migrate_product_metadata_clears_source_state_app_limit(tmp_path, monkeypatch):
    _configure_runtime_state_paths(tmp_path, monkeypatch, version='3.0.0')
    store = runtime_state_service.ProductRuntimeStateStore()
    migrated = runtime_state_service.migrate_product_runtime_state(source_state={
        'edition_key': 'enterprise',
        'max_apps': 10000,
        'state_source': 'legacy-migration',
        'updated_by': 'test',
    })

    assert migrated.key == 'enterprise'
    assert migrated.max_apps is None
    assert store.get_runtime_state_row()['max_apps'] is None


def test_migrate_product_metadata_rejects_nonstandard_legacy_max_apps(tmp_path, monkeypatch):
    _configure_runtime_state_paths(tmp_path, monkeypatch, version='3.0.0')
    legacy_ini_path = tmp_path / 'system.ini'
    legacy_ini_path.write_text('[max_apps]\nkey = 7\n', encoding='utf-8')

    try:
        product_metadata_service.migrate_product_metadata(
            version='3.0.0',
            legacy_system_ini_file=str(legacy_ini_path),
        )
    except ValueError as error:
        assert 'Unsupported legacy max_apps value' in str(error)
    else:
        raise AssertionError('Expected ValueError for nonstandard legacy max_apps')


@pytest.mark.parametrize("query", ["metadata", "edition", "settings", "overview"])
def test_cli_product_queries_only_open_existing_database_readonly(tmp_path, monkeypatch, query):
    import sqlite3
    from click.testing import CliRunner
    from unittest.mock import MagicMock
    from src.cli.overview_commands import overview_group
    from src.cli.settings_commands import settings_group
    from src.schemas.overview import OverviewAppsSummary
    from src.services.overview_service import OverviewService

    _configure_runtime_state_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("WEBSOFT9_APPHUB_CONFIG_PATH", str(tmp_path / "config.ini"))
    product_metadata_service.write_product_edition("starter")
    original_connect = sqlite3.connect
    opened = []

    def readonly_connect(database, *args, **kwargs):
        assert "?mode=ro" in str(database)
        assert kwargs.get("uri") is True
        opened.append(database)
        return original_connect(database, *args, **kwargs)

    def reject_initialization(_self):
        pytest.fail("Product query must not initialize or migrate storage")

    monkeypatch.setattr(sqlite3, "connect", readonly_connect)
    monkeypatch.setattr(runtime_state_service.ProductRuntimeStateStore, "_ensure_storage", reject_initialization)
    if query == "metadata":
        result = CliRunner().invoke(overview_group, ["edition", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["data"]["edition_key"] == "starter"
    elif query == "edition":
        assert product_metadata_service.read_product_edition(readonly=True).key == "starter"
    elif query == "settings":
        result = CliRunner().invoke(settings_group, ["summary", "--json"])
        assert result.exit_code == 0, result.output
        groups = json.loads(result.output)["data"]["groups"]
        version = next(group for group in groups if group["id"] == "version")
        assert version["items"][0]["metadata"]["edition_key"] == "starter"
    else:
        service = OverviewService(auth_service=MagicMock(), available_catalog_count_loader=lambda _locale: 0)
        summary = service._safe_product_summary(OverviewAppsSummary(), readonly=True)
        assert summary.available is True, summary.unavailable_reason
        assert summary.edition_key == "starter"
    assert opened


@pytest.mark.parametrize("storage", ["missing", "corrupt", "missing-table", "empty-state"])
def test_readonly_product_state_errors_do_not_create_or_repair_storage(tmp_path, monkeypatch, storage):
    import sqlite3
    from src.core.exception import CustomException

    _configure_runtime_state_paths(tmp_path, monkeypatch)
    database = tmp_path / "apphub-data" / "install-tracking.sqlite"
    if storage != "missing":
        database.parent.mkdir()
        if storage == "corrupt":
            database.write_bytes(b"invalid sqlite fixture")
        elif storage == "missing-table":
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE unrelated (id INTEGER)")
        else:
            runtime_state_service.ProductRuntimeStateStore()
    before = database.read_bytes() if database.exists() else None
    with pytest.raises(CustomException) as error:
        product_metadata_service.read_product_metadata(readonly=True)
    assert error.value.status_code == 503
    assert (database.read_bytes() if database.exists() else None) == before
    if storage == "missing":
        assert not database.parent.exists()