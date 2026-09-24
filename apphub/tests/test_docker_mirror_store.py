"""Accelerator storage, legacy import, and the resolution rules the console depends on."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.docker_mirror_store import (  # noqa: E402
    DockerMirrorStore,
    is_mirror_list_url,
    normalize_mirror_url,
    parse_mirror_entries,
)
from src.services.mirror_registry import MirrorRegistry  # noqa: E402


class _ConfigStub:
    def __init__(self, value: str):
        self.value = value

    def get_value(self, section: str, key: str) -> str:
        return self.value


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload
        self.url = ""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


@pytest.fixture()
def store(tmp_path) -> DockerMirrorStore:
    return DockerMirrorStore(tmp_path / "platform.sqlite")


@pytest.fixture()
def registry(tmp_path) -> MirrorRegistry:
    return MirrorRegistry(
        store=DockerMirrorStore(tmp_path / "platform.sqlite"),
        data_root=tmp_path,
    )


def _write_default_list(registry: MirrorRegistry, mirrors: list[str]) -> None:
    path = registry.default_list_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mirrors": mirrors}), encoding="utf-8")


# ── Parsing helpers ───────────────────────────────────────────────────────────


def test_normalize_mirror_url_strips_scheme_and_trailing_slash():
    assert normalize_mirror_url("https://docker.1ms.run/") == "docker.1ms.run"
    assert normalize_mirror_url("  docker.1ms.run  ") == "docker.1ms.run"


def test_parse_mirror_entries_splits_and_deduplicates():
    assert parse_mirror_entries("a\nb, c\n a") == ["a", "b", "c"]
    assert parse_mirror_entries("") == []


def test_is_mirror_list_url_detects_a_remote_list():
    assert is_mirror_list_url("https://artifact.websoft9.com/websoft9/dev/mirrors.json")
    assert not is_mirror_list_url("docker.1ms.run")


def test_database_path_honours_the_environment_override(tmp_path, monkeypatch):
    target = tmp_path / "custom" / "platform.sqlite"
    monkeypatch.setenv("WEBSOFT9_PLATFORM_DB_PATH", str(target))
    assert DockerMirrorStore().database_file == target


# ── Storage ───────────────────────────────────────────────────────────────────


def test_replace_entries_keeps_the_given_order(store: DockerMirrorStore):
    entries = store.replace_entries(
        [{"url": "docker.1ms.run"}, {"url": "docker.m.daocloud.io"}]
    )

    assert [entry.url for entry in entries] == ["docker.1ms.run", "docker.m.daocloud.io"]
    assert [entry.position for entry in entries] == [0, 1]


def test_replace_entries_ignores_duplicates_and_normalises_urls(store: DockerMirrorStore):
    entries = store.replace_entries(
        [{"url": "https://docker.1ms.run/"}, {"url": "docker.1ms.run"}]
    )

    assert [entry.url for entry in entries] == ["docker.1ms.run"]


def test_renaming_an_entry_keeps_its_credentials(store: DockerMirrorStore):
    """The id identifies the row, so an edited address must not lose the password."""
    created = store.replace_entries(
        [
            {
                "url": "old.example.com",
                "username": "ops",
                "password": "s3cret",
            }
        ]
    )

    renamed = store.replace_entries(
        [{"id": created[0].id, "url": "new.example.com", "username": "ops"}]
    )

    assert renamed[0].url == "new.example.com"
    assert renamed[0].password == "s3cret"


def test_replace_entries_rejects_an_address_docker_could_not_use(store: DockerMirrorStore):
    for invalid in ("ftp://mirror.example.com", "http://mirror.example.com", "not a host", "mirror"):
        with pytest.raises(ValueError):
            store.replace_entries([{"url": invalid}])


def test_replace_entries_accepts_an_explicit_https_address(store: DockerMirrorStore):
    """An HTTPS scheme is what Docker uses anyway, so it is normalised rather than refused."""
    entries = store.replace_entries([{"url": "https://docker.1ms.run/"}])

    assert [entry.url for entry in entries] == ["docker.1ms.run"]


def test_replace_entries_accepts_a_host_with_a_port_and_a_path(store: DockerMirrorStore):
    entries = store.replace_entries(
        [{"url": "registry.example.com:5000/docker"}, {"url": "docker.1ms.run"}]
    )

    assert [entry.url for entry in entries] == [
        "registry.example.com:5000/docker",
        "docker.1ms.run",
    ]


def test_lookup_password_finds_the_stored_password_by_id_then_url(store: DockerMirrorStore):
    created = store.replace_entries(
        [{"url": "old.example.com", "username": "ops", "password": "s3cret"}]
    )

    assert store.lookup_password(created[0].id, "renamed.example.com") == "s3cret"
    assert store.lookup_password(None, "old.example.com") == "s3cret"
    assert store.lookup_password(None, "unknown.example.com") == ""


def test_import_from_config_skips_addresses_docker_could_not_use(store: DockerMirrorStore):
    imported = store.import_from_config(
        _ConfigStub("docker.1ms.run\nftp://broken.example.com\nnot a host")
    )

    assert imported == 1
    assert [entry.url for entry in store.list_entries()] == ["docker.1ms.run"]


def test_omitted_password_keeps_the_stored_one_and_can_clear_a_public_entry(store: DockerMirrorStore):
    store.replace_entries(
        [{"url": "registry.example.com", "username": "ops", "password": "s3cret"}]
    )

    kept = store.replace_entries([{"url": "registry.example.com", "username": "ops"}])
    assert kept[0].password == "s3cret"

    cleared = store.replace_entries(
        [{"url": "registry.example.com", "username": "", "password": ""}]
    )
    assert cleared[0].password == ""


def test_replace_entries_requires_a_password_when_a_user_name_is_set(store: DockerMirrorStore):
    with pytest.raises(ValueError, match="password is required"):
        store.replace_entries([{"url": "registry.example.com", "username": "ops"}])


def test_disabled_entries_stay_stored_but_are_not_offered(store: DockerMirrorStore):
    store.replace_entries(
        [{"url": "docker.1ms.run", "enabled": False}, {"url": "docker.xuanyuan.me"}]
    )

    assert [entry.url for entry in store.list_entries()] == [
        "docker.1ms.run",
        "docker.xuanyuan.me",
    ]
    assert [entry.url for entry in store.list_enabled_entries()] == ["docker.xuanyuan.me"]


def test_replace_entries_survives_a_new_store_instance(store: DockerMirrorStore, tmp_path):
    store.replace_entries([{"url": "docker.1ms.run"}])

    reopened = DockerMirrorStore(tmp_path / "platform.sqlite")
    assert [entry.url for entry in reopened.list_entries()] == ["docker.1ms.run"]


# ── Legacy import ─────────────────────────────────────────────────────────────


def test_import_from_config_moves_the_list_once(store: DockerMirrorStore):
    imported = store.import_from_config(
        _ConfigStub("docker.1ms.run\ndocker.m.daocloud.io")
    )

    assert imported == 2
    assert [entry.url for entry in store.list_entries()] == [
        "docker.1ms.run",
        "docker.m.daocloud.io",
    ]

    # A second run must not resurrect or duplicate anything.
    assert store.import_from_config(_ConfigStub("docker.1ms.run")) == 0
    assert len(store.list_entries()) == 2


def test_import_from_config_never_overwrites_an_operator_list(store: DockerMirrorStore):
    store.replace_entries([{"url": "registry.example.com"}])

    assert store.import_from_config(_ConfigStub("docker.1ms.run")) == 0
    assert [entry.url for entry in store.list_entries()] == ["registry.example.com"]


def test_import_from_config_skips_a_list_url(store: DockerMirrorStore):
    value = "https://artifact.websoft9.com/websoft9/dev/mirrors.json"

    assert store.import_from_config(_ConfigStub(value)) == 0
    assert store.list_entries() == []


def test_import_from_config_does_not_come_back_after_the_list_was_cleared(
    store: DockerMirrorStore,
):
    """Clearing every row means "use the shipped list", not "import the old value again"."""
    store.import_from_config(_ConfigStub("docker.1ms.run"))
    store.replace_entries([])

    assert store.import_from_config(_ConfigStub("docker.1ms.run")) == 0
    assert store.list_entries() == []


def test_import_from_config_tolerates_a_missing_section(store: DockerMirrorStore):
    class _Raising:
        def get_value(self, section: str, key: str) -> str:
            raise KeyError(section)

    assert store.import_from_config(_Raising()) == 0


# ── Resolution ────────────────────────────────────────────────────────────────


def test_registry_prefers_the_operator_list_and_keeps_credentials(registry: MirrorRegistry):
    registry.store.replace_entries(
        [
            {"url": "registry.example.com", "username": "ops", "password": "s3cret"},
            {"url": "docker.1ms.run"},
        ]
    )
    _write_default_list(registry, ["default.example.com"])

    accelerators = registry.accelerators(refresh=False)

    assert [item.url for item in accelerators] == ["registry.example.com", "docker.1ms.run"]
    assert accelerators[0].auth_config() == {"username": "ops", "password": "s3cret"}
    assert accelerators[1].auth_config() is None
    assert registry.source() == "operator"


def test_registry_uses_the_default_list_when_nothing_is_configured(registry: MirrorRegistry):
    _write_default_list(registry, ["docker.1ms.run", "docker.xuanyuan.me"])

    accelerators = registry.accelerators(refresh=False)

    assert [item.url for item in accelerators] == ["docker.1ms.run", "docker.xuanyuan.me"]
    assert all(item.auth_config() is None for item in accelerators)
    assert registry.source() == "default"


def test_registry_returns_nothing_when_every_entry_is_disabled(registry: MirrorRegistry):
    registry.store.replace_entries([{"url": "docker.1ms.run", "enabled": False}])
    _write_default_list(registry, ["default.example.com"])

    # Disabling every entry is an explicit decision: the default list must not creep back in.
    assert registry.accelerators(refresh=False) == []
    assert registry.source() == "disabled"


def test_registry_credentials_only_answer_for_their_own_host(registry: MirrorRegistry):
    registry.store.replace_entries(
        [{"url": "registry.example.com", "username": "ops", "password": "s3cret"}]
    )

    assert registry.credentials_for("registry.example.com") == {
        "username": "ops",
        "password": "s3cret",
    }
    assert registry.credentials_for("docker.1ms.run") is None


def test_refresh_failure_keeps_the_previous_list(registry: MirrorRegistry, monkeypatch):
    _write_default_list(registry, ["docker.1ms.run"])
    before = registry.default_list_file.read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise RuntimeError("network is down")

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _boom)

    assert registry.refresh_default_list(force=True) is False
    assert registry.default_list_file.read_text(encoding="utf-8") == before


def test_refresh_writes_the_fetched_list_and_prefers_the_region_path(
    registry: MirrorRegistry, monkeypatch
):
    monkeypatch.setattr("src.services.mirror_registry.read_region", lambda: "cn")
    requested: list[str] = []

    def _get(url, *args, **kwargs):
        requested.append(url)
        return _FakeResponse({"mirrors": ["docker.1ms.run"]})

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _get)

    assert registry.refresh_default_list(force=True) is True
    assert requested[0].endswith("/cn/mirrors.json")
    assert json.loads(registry.default_list_file.read_text(encoding="utf-8"))["mirrors"] == [
        "docker.1ms.run"
    ]


def test_refresh_falls_back_to_the_channel_path_when_the_region_path_is_missing(
    registry: MirrorRegistry, monkeypatch
):
    monkeypatch.setattr("src.services.mirror_registry.read_region", lambda: "global")
    requested: list[str] = []

    def _get(url, *args, **kwargs):
        requested.append(url)
        if url.endswith("/global/mirrors.json"):
            raise RuntimeError("404")
        return _FakeResponse({"mirrors": ["docker.example.com"]})

    monkeypatch.setattr("src.services.mirror_registry.requests.get", _get)

    assert registry.refresh_default_list(force=True) is True
    assert requested == [
        "https://artifact.websoft9.com/websoft9/release/global/mirrors.json",
        "https://artifact.websoft9.com/websoft9/release/mirrors.json",
    ]


def test_host_visible_export_carries_addresses_without_credentials(registry: MirrorRegistry):
    registry.store.replace_entries(
        [{"url": "registry.example.com", "username": "ops", "password": "s3cret"}]
    )

    path = registry.export_host_visible_list()

    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mirrors"] == ["registry.example.com"]
    assert payload["source"] == "operator"
    assert "s3cret" not in path.read_text(encoding="utf-8")
