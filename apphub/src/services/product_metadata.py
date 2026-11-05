from src.services.product_runtime_state import (
    ProductRuntimeState as ProductEditionMetadata,
)
from src.services.product_runtime_state import (
    migrate_product_runtime_state,
    read_product_runtime_state,
    read_release_version,
    set_product_runtime_edition,
)


def read_product_metadata(*, readonly: bool = False) -> dict:
    state = read_product_runtime_state(readonly=True) if readonly else read_product_runtime_state()
    return {
        "version": state.version,
        "edition_key": state.edition_key,
        "edition_name": state.edition_name,
        "max_apps": state.max_apps,
        "state_source": state.state_source,
        "updated_by": state.updated_by,
        "updated_at": state.updated_at,
        "note": state.note,
    }


def read_product_metadata_file(_file_path: str) -> dict:
    return read_product_metadata()


def resolve_product_max_apps(edition_key):
    from src.core.product_catalog import resolve_product_edition_definition

    edition = resolve_product_edition_definition(edition_key)
    return edition.max_apps


def write_product_metadata(*, edition_key: str, version=None, max_apps=None) -> ProductEditionMetadata:
    if version is not None:
        import json
        from pathlib import Path

        version_file = Path(__file__).resolve().parents[3] / 'version.json'
        payload = {}
        if version_file.exists():
            try:
                payload = json.loads(version_file.read_text(encoding='utf-8'))
            except Exception:
                payload = {}
        payload['version'] = str(version).strip()
        payload.setdefault('channel', 'release')
        version_file.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding='utf-8')

    if max_apps is not None:
        from src.services.product_runtime_state import ProductRuntimeStateStore

        store = ProductRuntimeStateStore()
        store.write_runtime_state(
            edition_key=edition_key,
            max_apps=max_apps,
            state_source='manual-support',
            updated_by='system',
        )
        return read_product_runtime_state()

    return set_product_runtime_edition(edition_key, updated_by='system')


def write_product_edition(edition_key: str, version=None) -> ProductEditionMetadata:
    return write_product_metadata(edition_key=edition_key, version=version)


def migrate_product_metadata(
    *, version=None, source_metadata_file=None, legacy_system_ini_file=None, fallback_edition_key='free'
) -> ProductEditionMetadata:
    source_state = None
    if source_metadata_file:
        import json
        from pathlib import Path

        source_path = Path(source_metadata_file)
        if source_path.exists():
            try:
                source_state = json.loads(source_path.read_text(encoding='utf-8'))
            except Exception:
                source_state = None

    if version is not None:
        read_release_version()

    return migrate_product_runtime_state(
        version=version,
        source_state=source_state,
        legacy_system_ini_file=legacy_system_ini_file,
        fallback_edition_key=fallback_edition_key,
    )


def read_product_edition(*, readonly: bool = False) -> ProductEditionMetadata:
    return read_product_runtime_state(readonly=True) if readonly else read_product_runtime_state()
