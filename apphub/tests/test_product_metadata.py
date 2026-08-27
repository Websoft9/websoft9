import json
import sys
from pathlib import Path


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


def test_migrate_product_metadata_from_legacy_system_ini(tmp_path, monkeypatch):
    _configure_runtime_state_paths(tmp_path, monkeypatch, version='3.0.0')
    legacy_ini_path = tmp_path / 'system.ini'
    legacy_ini_path.write_text('[max_apps]\nkey = 10\n', encoding='utf-8')

    edition = product_metadata_service.migrate_product_metadata(
        version='3.0.0',
        legacy_system_ini_file=str(legacy_ini_path),
    )
    payload = product_metadata_service.read_product_metadata()

    assert edition.key == 'standard'
    assert edition.max_apps is None
    assert payload['version'] == '3.0.0'
    assert payload['edition_key'] == 'standard'
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