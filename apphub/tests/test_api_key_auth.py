"""The App Store endpoints must behave like the application ones behind the gateway.

Both are reached only through the platform gateway, which authenticates the
session and stamps the internal trust header. Keeping the App Store paths in the
same skip list means container-local calls (`:8080`) behave exactly like gateway
calls (`:9000`), which avoids "works in the console, 400 with curl" surprises.
"""

from __future__ import annotations

import pytest

from src.core.api_key_auth import should_skip_api_key_auth


@pytest.mark.parametrize(
    "path",
    [
        "/api/appstore/reload",
        "/appstore/reload",
        "/api/appstore/sync",
        "/api/appstore/state",
        "/api/appstore/sync/status",
        "/appstore",
    ],
)
def test_app_store_paths_skip_the_api_key_requirement(path):
    assert should_skip_api_key_auth(path) is True


@pytest.mark.parametrize(
    "path",
    ["/api/appstorex", "/api/appstoreful/reload", "/api/backup", "/api/scheduled-tasks"],
)
def test_neighbouring_paths_are_not_covered_by_the_prefix(path):
    assert should_skip_api_key_auth(path) is False


def test_the_application_paths_keep_their_existing_behaviour():
    assert should_skip_api_key_auth("/api/apps/local/refresh") is True
    assert should_skip_api_key_auth("/api/apps") is True
