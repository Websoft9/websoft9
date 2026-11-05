"""The files agent: the service that reads and writes application files for the console.

It has two halves and both matter:

* path handling — every request carries a client-supplied `root_path` and `path`, so a mistake here
  turns the console into an arbitrary-file API. The traversal and allowlist rules are asserted
  directly.
* the HTTP surface — a request is answered locally when the path exists on this host, and through a
  privileged Docker helper container when it only exists inside the host's Docker volumes. Both
  branches return the same shapes, which is what the console renders.
"""

import base64
import os
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src import files_agent
from src.core.exception import CustomException


@pytest.fixture
def agent(monkeypatch, tmp_path):
    """A files agent allowed to serve one temporary volume directory."""
    volume = tmp_path / "volume"
    volume.mkdir()
    monkeypatch.setenv("WEBSOFT9_FILES_AGENT_ALLOWED_ROOTS", str(volume))
    # 平台网关证书目录也被加入白名单,指向临时目录避免依赖真实环境
    monkeypatch.setenv("WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH", str(tmp_path / "gateway" / "cert.pem"))
    monkeypatch.setattr(files_agent, "_detect_docker_volumes_root", lambda: str(volume))
    # 两个白名单函数都带 lru_cache,只清一个会让上个用例的路径泄漏进来
    for cached in (files_agent._allowed_roots, files_agent._docker_allowed_roots):
        cache_clear = getattr(cached, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()
    client = TestClient(files_agent.app)
    yield SimpleNamespace(client=client, root=str(volume), volume=volume, tmp=tmp_path)
    for cached in (files_agent._allowed_roots, files_agent._docker_allowed_roots):
        cache_clear = getattr(cached, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()


def _root(agent):
    return str(agent.volume)


# ── relative paths ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/", "/"),
        ("", "/"),
        (None, "/"),
        ("a/b", "/a/b"),
        ("./a/./b", "/a/b"),
        ("/a//b/", "/a/b"),
        (" leading/trailing ", "/leading/trailing"),
    ],
)
def test_relative_paths_are_normalized(value, expected):
    assert files_agent._normalize_relative_path(value) == expected


@pytest.mark.parametrize("value", ["..", "../etc/passwd", "a/../../b", "/a/../.."])
def test_traversal_tokens_are_rejected_outright(value):
    with pytest.raises(CustomException) as error:
        files_agent._normalize_relative_path(value)

    assert error.value.status_code == 400
    assert "outside the allowed volume root" in error.value.details


# ── names ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["", "   ", "a/b", "a\\b", ".", ".."])
def test_invalid_names_are_rejected(value):
    with pytest.raises(CustomException) as error:
        files_agent._normalize_name(value)

    assert error.value.status_code == 400


def test_names_are_trimmed():
    assert files_agent._normalize_name("  report.txt  ") == "report.txt"


def test_item_paths_are_relative_to_the_root(tmp_path):
    root = tmp_path / "volume"
    assert files_agent._normalize_item_path(str(root), str(root)) == "/"
    assert files_agent._normalize_item_path(str(root), str(root / "a" / "b.txt")) == "/a/b.txt"


# ── root and target resolution ────────────────────────────────────────────


def test_a_relative_root_is_rejected(agent):
    with pytest.raises(CustomException) as error:
        files_agent._normalize_root_path("volume")

    assert error.value.status_code == 400


def test_a_root_outside_the_allowlist_is_rejected(agent):
    with pytest.raises(CustomException) as error:
        files_agent._normalize_root_path(str(agent.tmp / "elsewhere"))

    assert error.value.details == "Requested root path is outside the allowed files-agent roots"


def test_a_missing_root_inside_the_allowlist_but_outside_docker_is_rejected(agent):
    # 平台网关证书目录在白名单里,但它不是 Docker 卷,无法交给 helper 处理
    with pytest.raises(CustomException) as error:
        files_agent._normalize_root_path(str(agent.tmp / "gateway" / "missing"))

    assert error.value.status_code == 404
    assert error.value.details == "The requested root path does not exist"


def test_an_existing_root_is_accepted(agent):
    assert files_agent._normalize_root_path(_root(agent)) == os.path.realpath(_root(agent))


def test_the_helper_is_only_used_for_missing_roots(agent):
    assert files_agent._should_use_helper_root(_root(agent)) is False
    assert files_agent._should_use_helper_root(str(agent.volume / "missing")) is True
    assert files_agent._should_use_helper_root(str(agent.tmp / "elsewhere")) is False


def test_target_paths_stay_inside_the_root(agent):
    (agent.volume / "a.txt").write_text("x")

    target = files_agent._resolve_target_path(_root(agent), "/a.txt")

    assert target == os.path.realpath(str(agent.volume / "a.txt"))


def test_a_symlink_that_escapes_the_root_is_rejected(agent):
    outside = agent.tmp / "outside.txt"
    outside.write_text("secret")
    (agent.volume / "escape").symlink_to(outside)

    with pytest.raises(CustomException) as error:
        files_agent._resolve_target_path(_root(agent), "/escape")

    assert error.value.details == "Requested path resolves outside the allowed volume root"


def test_a_missing_target_is_reported_as_not_found(agent):
    with pytest.raises(CustomException) as error:
        files_agent._resolve_target_path(_root(agent), "/nope.txt")

    assert error.value.status_code == 404


def test_the_root_itself_is_not_allowed_where_a_child_is_required(agent):
    with pytest.raises(CustomException) as error:
        files_agent._resolve_target_path(_root(agent), "/", allow_root=False)

    assert error.value.details == "The volume root is not a valid target for this operation"


# ── metadata ──────────────────────────────────────────────────────────────


def test_text_editability_requires_a_small_regular_file():
    import stat

    regular = stat.S_IFREG | 0o644
    assert files_agent._infer_text_editable("a.txt", "file", 10, regular) is True
    assert files_agent._infer_text_editable("a.txt", "file", files_agent.TEXT_FILE_LIMIT_BYTES, regular) is True
    assert files_agent._infer_text_editable("big.bin", "file", files_agent.TEXT_FILE_LIMIT_BYTES + 1, regular) is False
    assert files_agent._infer_text_editable("dir", "directory", 0, regular) is False
    assert files_agent._infer_text_editable("pipe", "file", 0, stat.S_IFIFO | 0o644) is False


def test_timestamps_are_iso_utc():
    assert files_agent._format_timestamp(0) == "1970-01-01T00:00:00Z"


def test_metadata_describes_a_file(agent):
    target = agent.volume / "report.txt"
    target.write_text("hello")
    attributes = os.stat(target)

    metadata = files_agent._build_metadata(str(target), _root(agent), "", attributes, include_identity_ids=True)

    assert metadata["name"] == "report.txt"
    assert metadata["path"] == "/report.txt"
    assert metadata["item_type"] == "file"
    assert metadata["size"] == 5
    assert metadata["text_editable"] is True
    assert "(" in metadata["owner"] and ")" in metadata["owner"]


def test_metadata_for_the_root_uses_the_display_name(agent):
    attributes = os.stat(agent.volume)

    metadata = files_agent._build_metadata(
        os.path.realpath(_root(agent)), _root(agent), "my-app", attributes, include_identity_ids=False
    )

    # 卷根目录没有 basename,名称由前端传进来
    assert metadata["name"] == "my-app"
    assert metadata["path"] == "/"
    assert metadata["item_type"] == "directory"


def test_metadata_without_identity_ids_omits_the_number(agent):
    target = agent.volume / "a.txt"
    target.write_text("x")

    metadata = files_agent._build_metadata(str(target), _root(agent), "", os.stat(target), include_identity_ids=False)

    assert "(" not in metadata["owner"]


# ── helper output parsing ─────────────────────────────────────────────────


def test_helper_output_must_not_be_empty():
    with pytest.raises(CustomException) as error:
        files_agent.DockerHelperManager._parse_output("")

    assert error.value.status_code == 500
    assert error.value.details == "Docker helper returned no output"


def test_invalid_helper_output_is_reported_with_the_raw_text():
    with pytest.raises(CustomException) as error:
        files_agent.DockerHelperManager._parse_output("not json")

    assert error.value.status_code == 500
    assert error.value.details.startswith("Invalid Docker helper response:")
    assert "not json" in error.value.details


def test_helper_failures_keep_their_status_and_message():
    payload = '{"ok": false, "status_code": 404, "message": "File Not Found", "details": "gone"}'

    with pytest.raises(CustomException) as error:
        files_agent.DockerHelperManager._parse_output(payload)

    assert (error.value.status_code, error.value.message, error.value.details) == (404, "File Not Found", "gone")


def test_helper_failures_default_to_a_server_error():
    with pytest.raises(CustomException) as error:
        files_agent.DockerHelperManager._parse_output('{"ok": false}')

    assert error.value.status_code == 500
    assert error.value.message == "File Operation Error"


def test_helper_success_returns_the_data_object():
    assert files_agent.DockerHelperManager._parse_output('{"ok": true, "data": {"items": []}}') == {"items": []}


def test_helper_success_wraps_a_scalar_value():
    assert files_agent.DockerHelperManager._parse_output('{"ok": true, "data": 3}') == {"value": 3}


# ── helper container lifecycle ────────────────────────────────────────────


def _manager(**overrides):
    """A manager without the background sweeper thread or the constructor's Docker probe."""
    manager = object.__new__(files_agent.DockerHelperManager)
    manager.docker_client = overrides.get("client")
    manager.helper_image = overrides.get("helper_image", "websoft9dev/websoft9:dev")
    manager.idle_ttl_seconds = overrides.get("idle_ttl_seconds", 300)
    manager._lock = threading.Lock()
    manager._helpers = overrides.get("helpers", {})
    manager._sweeper_started = False
    return manager


class FakeExecResult:
    def __init__(self, output):
        self.output = output


class FakeContainer:
    def __init__(self, container_id="abc123", output=b'{"ok": true, "data": {}}', error=None):
        self.id = container_id
        self.output = output
        self.error = error
        self.exec_calls = []
        self.removed = []
        self.attrs = {'Config': {'Labels': {}}}

    def exec_run(self, command, environment=None):
        self.exec_calls.append({'command': command, 'environment': environment})
        if self.error:
            raise self.error
        return FakeExecResult(self.output)

    def remove(self, force=False):
        self.removed.append(force)


def test_execute_passes_the_action_and_mount_path(agent):
    container = FakeContainer(output=b'{"ok": true, "data": {"items": [1]}}')
    manager = _manager()
    manager._ensure_container = lambda root_path: container

    result = manager.execute(_root(agent), "directory", {"path": "/"})

    assert result == {"items": [1]}
    command = container.exec_calls[0]['command']
    assert command[3] == 'directory'
    # payload 以 base64 传给 helper,避免引号/编码问题
    assert __import__("json").loads(base64.b64decode(command[4])) == {"path": "/"}
    assert container.exec_calls[0]['environment'] == {"WEBSOFT9_FILE_HELPER_ROOT": files_agent.DOCKER_HELPER_MOUNT_PATH}


def test_a_failing_helper_call_drops_the_container(agent):
    container = FakeContainer(error=RuntimeError('container is gone'))
    manager = _manager()
    manager._ensure_container = lambda root_path: container
    dropped = []
    manager._drop_container = lambda root_path, force_remove=False: dropped.append((root_path, force_remove))

    with pytest.raises(CustomException) as error:
        manager.execute(_root(agent), "directory", {})

    assert error.value.status_code == 500
    assert 'container is gone' in error.value.details
    assert dropped == [(_root(agent), True)]


def test_a_running_helper_container_is_reused(agent):
    container = FakeContainer()
    manager = _manager(helpers={_root(agent): {'container_id': 'abc123', 'last_used': time.monotonic()}})
    manager._load_running_container = lambda container_id: container
    manager._create_container = lambda root_path: pytest.fail('a live container must be reused')

    assert manager._ensure_container(_root(agent)) is container
    assert manager._helpers[_root(agent)]['last_used'] > 0


def test_a_stopped_helper_container_is_replaced(agent):
    old = FakeContainer(container_id='old')
    new = FakeContainer(container_id='new')
    manager = _manager(helpers={_root(agent): {'container_id': 'old', 'last_used': time.monotonic()}})
    manager._load_running_container = lambda container_id: None
    manager._create_container = lambda root_path: new
    removed = []
    manager._remove_container = lambda container_id: removed.append(container_id)

    assert manager._ensure_container(_root(agent)) is new
    assert manager._helpers[_root(agent)]['container_id'] == 'new'
    assert old.removed == []


def test_idle_helpers_are_pruned(agent):
    manager = _manager(
        helpers={
            'stale': {'container_id': 'stale-id', 'last_used': time.monotonic() - 10_000},
            'fresh': {'container_id': 'fresh-id', 'last_used': time.monotonic()},
        }
    )
    removed = []
    manager._remove_container = lambda container_id: removed.append(container_id)

    manager._prune_stale_locked()

    assert removed == ['stale-id']
    assert list(manager._helpers) == ['fresh']


def test_orphaned_helpers_are_removed_but_known_ones_are_kept(agent):
    known = FakeContainer(container_id='known')
    orphan = FakeContainer(container_id='orphan')
    manager = _manager(
        client=SimpleNamespace(
            containers=SimpleNamespace(
                list=lambda all=False, filters=None: [known, orphan],
            )
        ),
        helpers={_root(agent): {'container_id': 'known'}},
    )
    removed = []
    manager._remove_container = lambda container_id: removed.append(container_id)

    manager.prune_orphaned_helpers()

    assert removed == ['orphan']


def test_orphan_pruning_survives_a_broken_docker_socket():
    manager = _manager(
        client=SimpleNamespace(
            containers=SimpleNamespace(list=lambda all=False, filters=None: (_ for _ in ()).throw(RuntimeError('socket gone')))
        )
    )

    manager.prune_orphaned_helpers()


def test_helper_image_prefers_the_published_platform_image():
    images = [
        SimpleNamespace(tags=['other:latest']),
        SimpleNamespace(tags=['websoft9dev/websoft9:2.0.0']),
    ]
    manager = _manager(
        client=SimpleNamespace(images=SimpleNamespace(list=lambda name=None: images)),
        helper_image=None,
    )

    assert manager._get_helper_image() == 'websoft9dev/websoft9:2.0.0'


def test_helper_image_falls_back_to_the_public_python_image():
    manager = _manager(
        client=SimpleNamespace(images=SimpleNamespace(list=lambda name=None: (_ for _ in ()).throw(RuntimeError('x')))),
        helper_image=None,
    )

    assert manager._get_helper_image() == files_agent.DOCKER_HELPER_IMAGE_FALLBACK


# ── helper container creation ─────────────────────────────────────────────


class FakeContainersApi:
    def __init__(self, run_error=None, existing=None):
        self.run_calls = []
        self.get_calls = []
        self.run_error = run_error
        self.existing = existing

    def run(self, image, **kwargs):
        self.run_calls.append({"image": image, **kwargs})
        # 只在第一次调用失败:拉取镜像后的重试必须成功
        if self.run_error and len(self.run_calls) == 1:
            raise self.run_error
        return FakeContainer(container_id="created")

    def get(self, ref):
        self.get_calls.append(ref)
        if isinstance(self.existing, Exception):
            raise self.existing
        return self.existing


def test_helper_container_is_named_and_labelled_for_its_root(agent):
    containers = FakeContainersApi()
    manager = _manager(
        client=SimpleNamespace(
            containers=containers,
            images=SimpleNamespace(list=lambda name=None: []),
        ),
        helper_image="websoft9dev/websoft9:dev",
    )

    container = manager._create_container(_root(agent))

    assert container.id == "created"
    call = containers.run_calls[0]
    assert call["image"] == "websoft9dev/websoft9:dev"
    assert call["name"].startswith("websoft9-files-helper-")
    assert call["labels"] == {"com.websoft9.role": "files-helper", "com.websoft9.files-root": _root(agent)}
    assert call["volumes"] == {_root(agent): {"bind": files_agent.DOCKER_HELPER_MOUNT_PATH, "mode": "rw"}}
    assert call["user"] == "0:0"
    # 旧的同名容器先被清掉,避免 name 冲突
    assert containers.get_calls == [call["name"]]


def test_a_missing_helper_image_is_pulled_first(agent):
    import docker

    containers = FakeContainersApi(run_error=docker.errors.ImageNotFound("missing"))
    pull_calls = []
    manager = _manager(
        client=SimpleNamespace(
            containers=containers,
            images=SimpleNamespace(list=lambda name=None: [], pull=lambda image: pull_calls.append(image)),
        ),
        helper_image="websoft9dev/websoft9:dev",
    )

    manager._create_container(_root(agent))

    assert pull_calls == ["websoft9dev/websoft9:dev"]
    assert len(containers.run_calls) == 2


def test_a_failing_helper_start_is_a_server_error(agent):
    manager = _manager(
        client=SimpleNamespace(
            containers=FakeContainersApi(run_error=RuntimeError("no space left")),
            images=SimpleNamespace(list=lambda name=None: []),
        ),
        helper_image="websoft9dev/websoft9:dev",
    )

    with pytest.raises(CustomException) as error:
        manager._create_container(_root(agent))

    assert error.value.status_code == 500
    assert "no space left" in error.value.details


def test_a_running_container_is_loaded_again(agent):
    running = FakeContainer()
    running.reload = lambda: None
    running.attrs = {"State": {"Running": True}}
    manager = _manager(client=SimpleNamespace(containers=FakeContainersApi(existing=running)))

    assert manager._load_running_container("abc123") is running


def test_a_container_that_is_not_running_is_not_reused(agent):
    stopped = FakeContainer()
    stopped.reload = lambda: None
    stopped.attrs = {"State": {"Running": False}}
    manager = _manager(client=SimpleNamespace(containers=FakeContainersApi(existing=stopped)))

    assert manager._load_running_container("abc123") is None
    assert manager._load_running_container(None) is None


def test_an_unknown_container_reference_yields_nothing(agent):
    manager = _manager(client=SimpleNamespace(containers=FakeContainersApi(existing=RuntimeError("gone"))))

    assert manager._load_running_container("missing") is None


def test_dropping_a_container_removes_it_only_when_forced(agent):
    removed = []
    manager = _manager(helpers={_root(agent): {"container_id": "abc123"}})
    manager._remove_container = lambda container_id: removed.append(container_id)

    manager._drop_container(_root(agent), force_remove=False)
    assert removed == []
    assert manager._helpers == {}

    manager._helpers[_root(agent)] = {"container_id": "def456"}
    manager._drop_container(_root(agent), force_remove=True)
    assert removed == ["def456"]


def test_removing_a_container_swallows_docker_errors(agent):
    container = FakeContainer()
    manager = _manager(client=SimpleNamespace(containers=FakeContainersApi(existing=container)))

    manager._remove_container("abc123")
    manager._remove_container(None)

    assert container.removed == [True]


def test_removing_a_missing_container_is_silent(agent):
    manager = _manager(client=SimpleNamespace(containers=FakeContainersApi(existing=RuntimeError("gone"))))

    manager._remove_container("abc123")
