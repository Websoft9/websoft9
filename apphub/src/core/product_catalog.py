from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProductEditionDefinition:
    key: str
    names: dict[str, str]
    max_apps: Optional[int] = None


PRODUCT_EDITIONS: dict[str, ProductEditionDefinition] = {
    "free": ProductEditionDefinition(
        key="free",
        names={
            "en": "Free",
            "zh-CN": "免费版",
        },
        max_apps=2,
    ),
    "starter": ProductEditionDefinition(
        key="starter",
        names={
            "en": "Starter",
            "zh-CN": "入门版",
        },
        max_apps=3,
    ),
    "standard": ProductEditionDefinition(
        key="standard",
        names={
            "en": "Standard",
            "zh-CN": "标准版",
        },
        max_apps=10,
    ),
    "enterprise": ProductEditionDefinition(
        key="enterprise",
        names={
            "en": "Enterprise",
            "zh-CN": "企业版",
        },
        max_apps=None,
    ),
}

PRODUCT_EDITION_ALIASES: dict[str, str] = {
    "open-source": "free",
    "professional": "standard",
}


def resolve_product_edition_definition(edition_key: Optional[str]) -> ProductEditionDefinition:
    normalized_key = (edition_key or "").strip() or "free"
    canonical_key = PRODUCT_EDITION_ALIASES.get(normalized_key, normalized_key)
    return PRODUCT_EDITIONS.get(canonical_key, PRODUCT_EDITIONS["free"])