import json
import os
from dataclasses import dataclass
from typing import Optional

from src.core.product_catalog import resolve_product_edition_definition

PRODUCT_METADATA_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../config/product_metadata.json")
)


@dataclass(frozen=True)
class ProductEditionMetadata:
    key: str
    name: str
    names: dict[str, str]
    max_apps: Optional[int]


def _read_json_file(file_path: str) -> dict:
    if not os.path.exists(file_path):
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def read_product_metadata() -> dict:
    return _read_json_file(PRODUCT_METADATA_FILE)


def read_product_edition() -> ProductEditionMetadata:
    metadata_payload = read_product_metadata()
    legacy_edition_payload = metadata_payload.get("edition") or {}
    edition_key = metadata_payload.get("edition_key") or legacy_edition_payload.get("key")
    edition_definition = resolve_product_edition_definition(
        edition_key if isinstance(edition_key, str) else None
    )
    names = dict(edition_definition.names)
    default_name = names.get("en") or names.get("zh-CN") or edition_definition.key

    return ProductEditionMetadata(
        key=edition_definition.key,
        name=default_name,
        names=names,
        max_apps=edition_definition.max_apps if isinstance(edition_definition.max_apps, int) and edition_definition.max_apps > 0 else None,
    )