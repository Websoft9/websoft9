"""The accelerator endpoints the console talks to.

The console never receives a stored password, so these tests also pin the contract that makes
editing an entry safe: an omitted password keeps the stored one, and a re-test of an unchanged
entry still presents the stored credentials.
"""

import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

router_module = importlib.import_module("src.api.v1.routers.settings")

from src.schemas.appSettings import (  # noqa: E402
    DockerMirrorEntriesRequest,
    DockerMirrorEntryPayload,
)
from src.core.exception import CustomException  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_PLATFORM_DB_PATH", str(tmp_path / "platform.sqlite"))
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path))


def _request(*entries: dict) -> DockerMirrorEntriesRequest:
    return DockerMirrorEntriesRequest(
        entries=[DockerMirrorEntryPayload(**entry) for entry in entries]
    )


# What Docker Hub style registries answer the version endpoint with: not a failure, an
# invitation to ask their token endpoint.
_CHALLENGE = 'Bearer realm="https://auth.example.test/token",service="registry.example.test"'


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self.payload = payload or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
        return None

    def json(self):
        return self.payload


def test_put_then_get_never_returns_the_stored_password():
    router_module.put_docker_mirror_entries(
        _request({"url": "registry.example.test", "username": "ops", "password": "s3cret"})
    )

    payload = router_module.get_docker_mirror_entries()

    assert payload["source"] == "operator"
    assert payload["entries"][0]["url"] == "registry.example.test"
    assert payload["entries"][0]["username"] == "ops"
    assert payload["entries"][0]["password_set"] is True
    assert "password" not in payload["entries"][0]


def test_put_replaces_the_whole_list_in_the_given_order():
    router_module.put_docker_mirror_entries(_request({"url": "first.example.test"}))
    router_module.put_docker_mirror_entries(
        _request({"url": "second.example.test"}, {"url": "third.example.test"})
    )

    urls = [entry["url"] for entry in router_module.get_docker_mirror_entries()["entries"]]

    assert urls == ["second.example.test", "third.example.test"]


def test_put_without_a_password_keeps_the_stored_one():
    router_module.put_docker_mirror_entries(
        _request({"url": "registry.example.test", "username": "ops", "password": "s3cret"})
    )

    router_module.put_docker_mirror_entries(
        _request({"url": "registry.example.test", "username": "ops"})
    )

    entry = router_module.get_docker_mirror_entries()["entries"][0]
    assert entry["password_set"] is True


def test_an_unconfigured_platform_reports_the_default_source():
    payload = router_module.get_docker_mirror_entries()

    assert payload["source"] == "default"
    assert payload["entries"] == []


def test_every_entry_disabled_reports_the_disabled_source():
    router_module.put_docker_mirror_entries(
        _request({"url": "registry.example.test", "enabled": False})
    )

    assert router_module.get_docker_mirror_entries()["source"] == "disabled"


def test_test_endpoint_presents_the_stored_password(monkeypatch):
    router_module.put_docker_mirror_entries(
        _request({"url": "registry.example.test", "username": "ops", "password": "s3cret"})
    )
    seen: dict = {}

    def _get(url, **kwargs):
        seen["url"] = url
        seen["auth"] = kwargs.get("auth")
        return _FakeResponse(200)

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _get)

    result = router_module.test_docker_mirror_entry(
        DockerMirrorEntryPayload(url="registry.example.test", username="ops")
    )

    assert seen["url"] == "https://registry.example.test/v2/"
    assert seen["auth"] == ("ops", "s3cret")
    assert result["reachable"] is True
    assert result["authorized"] is True


def test_test_endpoint_reports_rejected_credentials(monkeypatch):
    def _get(url, **kwargs):
        if url.endswith("/v2/"):
            return _FakeResponse(401, headers={"Www-Authenticate": _CHALLENGE})
        return _FakeResponse(401)

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _get)

    result = router_module.test_docker_mirror_entry(
        DockerMirrorEntryPayload(url="registry.example.test", username="ops", password="wrong")
    )

    assert result["reachable"] is True
    assert result["reason"] == "credentials-rejected"
    assert result["usable"] is False


def test_test_endpoint_reads_a_login_challenge_as_usable(monkeypatch):
    """A Docker Hub style mirror wants a token; that is not a broken accelerator."""
    monkeypatch.setattr(
        "src.services.mirror_registry.requests.get",
        lambda url, **kwargs: _FakeResponse(401, headers={"Www-Authenticate": _CHALLENGE}),
    )

    result = router_module.test_docker_mirror_entry(
        DockerMirrorEntryPayload(url="registry.example.test")
    )

    assert result["reachable"] is True
    assert result["reason"] == "credentials-required"
    assert result["usable"] is True


def test_test_endpoint_reports_an_unverifiable_password_separately(monkeypatch):
    """A token service that cannot be reached must not look like a wrong password."""

    def _get(url, **kwargs):
        if url.endswith("/v2/"):
            return _FakeResponse(401, headers={"Www-Authenticate": _CHALLENGE})
        raise RuntimeError("token service is unreachable")

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _get)

    result = router_module.test_docker_mirror_entry(
        DockerMirrorEntryPayload(url="registry.example.test", username="ops", password="s3cret")
    )

    assert result["reason"] == "error"
    assert result["usable"] is False
    assert "token endpoint" in result["detail"]


def test_put_rejects_an_accelerator_docker_could_not_use():
    with pytest.raises(CustomException) as failure:
        router_module.put_docker_mirror_entries(_request({"url": "http://mirror.example.test"}))

    assert failure.value.status_code == 400
    assert "HTTPS" in failure.value.details
    assert router_module.get_docker_mirror_entries()["entries"] == []


def test_put_rejects_a_user_name_without_a_password():
    with pytest.raises(CustomException) as failure:
        router_module.put_docker_mirror_entries(
            _request({"url": "registry.example.test", "username": "ops"})
        )

    assert failure.value.status_code == 400
    assert "password is required" in failure.value.details


def test_put_keeps_the_password_when_the_address_is_renamed():
    created = router_module.put_docker_mirror_entries(
        _request({"url": "old.example.test", "username": "ops", "password": "s3cret"})
    )
    entry_id = created["entries"][0]["id"]

    renamed = router_module.put_docker_mirror_entries(
        _request({"id": entry_id, "url": "new.example.test", "username": "ops"})
    )

    assert renamed["entries"][0]["url"] == "new.example.test"
    assert renamed["entries"][0]["password_set"] is True


def test_test_endpoint_reuses_the_password_of_a_renamed_entry(monkeypatch):
    created = router_module.put_docker_mirror_entries(
        _request({"url": "old.example.test", "username": "ops", "password": "s3cret"})
    )
    entry_id = created["entries"][0]["id"]
    seen: dict = {}

    def _get(url, **kwargs):
        seen["auth"] = kwargs.get("auth")
        return _FakeResponse(200)

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _get)

    router_module.test_docker_mirror_entry(
        DockerMirrorEntryPayload(id=entry_id, url="new.example.test", username="ops")
    )

    assert seen["auth"] == ("ops", "s3cret")


def test_test_endpoint_accepts_credentials_through_the_token_endpoint(monkeypatch):
    def _get(url, **kwargs):
        if url.endswith("/v2/"):
            return _FakeResponse(401, headers={"Www-Authenticate": _CHALLENGE})
        assert kwargs.get("auth") == ("ops", "s3cret")
        return _FakeResponse(200, {"token": "granted"})

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _get)

    result = router_module.test_docker_mirror_entry(
        DockerMirrorEntryPayload(url="registry.example.test", username="ops", password="s3cret")
    )

    assert result["reason"] == "ok"
    assert result["usable"] is True


def test_refresh_endpoint_reports_the_fetched_list(monkeypatch):
    monkeypatch.setattr(
        "src.services.mirror_registry.requests.get",
        lambda url, **kwargs: _FakeResponse(200, {"mirrors": ["docker.1ms.run"]}),
    )

    result = router_module.refresh_docker_mirror_defaults()

    assert result["refreshed"] is True
    assert result["mirrors"] == ["docker.1ms.run"]
