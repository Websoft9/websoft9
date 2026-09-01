import sys
from pathlib import Path

import pytest


if sys.version_info < (3, 10):
    pytestmark = pytest.mark.skip(reason='setup wizard version tests require Python 3.10+ type syntax support')


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if sys.version_info >= (3, 10):
    from src.services.setup_wizard import _get_default_edition


def test_setup_default_edition_prefers_highest_community_version_over_latest():
    assert _get_default_edition([
        {"key": "enterprise", "value": ["99.0.0"]},
        {"key": "community", "value": ["6.2.8", "latest", "6.3.0"]},
    ]) == "6.3.0"


def test_setup_default_edition_falls_back_to_latest_without_numeric_versions():
    assert _get_default_edition([
        {"key": "community", "value": ["latest"]},
    ]) == "latest"


def test_setup_default_edition_does_not_select_enterprise_versions():
    with pytest.raises(Exception):
        _get_default_edition([
            {"key": "enterprise", "value": ["99.0.0"]},
        ])


def test_setup_default_edition_uses_available_non_numeric_version():
    assert _get_default_edition([
        {"key": "community", "value": ["stable", "latest"]},
    ]) == "stable"


def test_setup_default_edition_rejects_missing_distribution_data():
    with pytest.raises(Exception):
        _get_default_edition(None)