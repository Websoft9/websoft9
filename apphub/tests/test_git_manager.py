import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.git_url_resolver import normalize_runtime_git_url


def test_normalize_runtime_git_url_maps_legacy_gitea_host_in_single_container_runtime(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_RUNTIME_LAYOUT", "single-container-target")
    monkeypatch.setenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN", "http://47.239.243.133:9000")

    assert (
        normalize_runtime_git_url("http://websoft9-git:3000/websoft9/moodle_ntg2o.git")
        == "http://127.0.0.1:3001/websoft9/moodle_ntg2o.git"
    )


def test_normalize_runtime_git_url_strips_w9git_prefix_for_internal_clone(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_RUNTIME_LAYOUT", "single-container-target")
    monkeypatch.setenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN", "http://47.239.243.133:9000")

    assert (
        normalize_runtime_git_url("http://127.0.0.1:9000/w9git/websoft9/moodle_ntg2o.git")
        == "http://127.0.0.1:3001/websoft9/moodle_ntg2o.git"
    )


def test_gitea_manager_lists_sorts_reads_and_writes_repository_files():
    import base64
    from types import SimpleNamespace

    import pytest

    from src.core.exception import CustomException
    from src.services.gitea_manager import GiteaManager

    manager = GiteaManager.__new__(GiteaManager)
    updated_calls = []

    class FakeGitea:
        def get_repo_tree(self, repo_name, ref="main", recursive=True):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "sha": "commit-head-1",
                    "tree": [
                        {"path": "README.md", "type": "blob", "size": 100, "sha": "sha-readme"},
                        {"path": ".env", "type": "blob", "size": 200, "sha": "sha-env"},
                        {"path": "docker-compose.yml", "type": "blob", "size": 300, "sha": "sha-compose"},
                        {"path": "src/.websoft9/access-profile.json", "type": "blob", "size": 50, "sha": "sha-hidden"},
                    ],
                },
            )

        def get_file_content_from_repo(self, repo_name, file_path):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "name": file_path,
                    "encoding": "base64",
                    "sha": "sha-env",
                    "content": base64.b64encode(b"W9_ID=demo\n").decode("utf-8"),
                },
            )

        def update_file_content_in_repo(self, repo_name, file_path, content, sha):
            updated_calls.append((repo_name, file_path, base64.b64decode(content).decode("utf-8"), sha))
            return SimpleNamespace(
                status_code=200,
                text="{}",
                json=lambda: {"content": {"sha": "sha-env-new"}, "commit": {"sha": "commit-head-2"}},
            )

    manager.gitea = FakeGitea()

    tree = manager.list_repo_files("demo_app")
    assert tree["head_sha"] == "commit-head-1"
    assert [item["path"] for item in tree["files"]] == [".env", "docker-compose.yml", "README.md"]

    read_res = manager.read_repo_text_file("demo_app", ".env")
    assert read_res == {"path": ".env", "name": ".env", "sha": "sha-env", "content": "W9_ID=demo\n"}

    write_res = manager.write_repo_text_file("demo_app", ".env", "W9_ID=updated\n", "sha-env")
    assert write_res == {"path": ".env", "sha": "sha-env-new", "head_sha": "commit-head-2"}
    assert updated_calls == [("demo_app", ".env", "W9_ID=updated\n", "sha-env")]

    with pytest.raises(CustomException):
        manager.read_repo_text_file("demo_app", "../outside")
    with pytest.raises(CustomException):
        manager.read_repo_text_file("demo_app", "src/.websoft9/access-profile.json")


# ── GitManager: 本地仓库初始化与推送 ──────────────────────────────────────


class _FakeConfigWriter:
    def __init__(self, values):
        self.values = values
        self.released = False

    def set_value(self, section, key, value):
        self.values[(section, key)] = value

    def release(self):
        self.released = True


class _FakeGit:
    def __init__(self, errors=None):
        self.calls = []
        self.errors = errors or {}

    def add(self, *args):
        self.calls.append(("add", args))
        if "add" in self.errors:
            raise self.errors["add"]

    def commit(self, *args):
        self.calls.append(("commit", args))
        if "commit" in self.errors:
            raise self.errors["commit"]

    def push(self, *args):
        self.calls.append(("push", args))
        if "push" in self.errors:
            raise self.errors["push"]


class _FakeRepo:
    created = []
    cloned = []
    instances = []

    def __init__(self, path):
        self.path = path
        self.git = _FakeGit()
        self.remotes = []
        self.config_values = {}
        _FakeRepo.instances.append(self)

    @classmethod
    def init(cls, path):
        if "init" in cls.created_errors:
            raise cls.created_errors["init"]
        instance = cls(path)
        cls.created.append(path)
        return instance

    @classmethod
    def clone_from(cls, url, path):
        if "clone" in cls.created_errors:
            raise cls.created_errors["clone"]
        cls.cloned.append((url, path))
        return cls(path)

    def config_writer(self):
        self.writer = _FakeConfigWriter(self.config_values)
        return self.writer

    def create_remote(self, name, url):
        if "remote" in _FakeRepo.created_errors:
            raise _FakeRepo.created_errors["remote"]
        self.remotes.append((name, url))


def _git_manager(monkeypatch, tmp_path, errors=None):
    from types import SimpleNamespace

    from src.services import git_manager as git_module

    _FakeRepo.created = []
    _FakeRepo.cloned = []
    _FakeRepo.instances = []
    _FakeRepo.created_errors = errors or {}
    monkeypatch.setattr(git_module, "Repo", _FakeRepo)
    monkeypatch.setattr(
        git_module,
        "IntegrationCredentialProvider",
        lambda: SimpleNamespace(get_gitea_credentials=lambda: SimpleNamespace(username="websoft9", email="dev@websoft9.com")),
    )
    return git_module.GitManager(str(tmp_path))


def test_git_init_requires_an_existing_directory(monkeypatch, tmp_path):
    import pytest

    from src.core.exception import CustomException

    manager = _git_manager(monkeypatch, tmp_path / "missing")

    with pytest.raises(CustomException):
        manager.init_local_repo_from_dir()


def test_git_init_configures_the_committer_and_commits(monkeypatch, tmp_path):
    manager = _git_manager(monkeypatch, tmp_path)

    manager.init_local_repo_from_dir()

    repo = _FakeRepo.instances[0]
    assert repo.config_values[("user", "name")] == "websoft9"
    assert repo.config_values[("user", "email")] == "dev@websoft9.com"
    assert repo.writer.released is True
    assert repo.git.calls == [("add", (".",)), ("commit", ("-m", "Initial commit"))]


def test_git_init_wraps_a_failed_commit(monkeypatch, tmp_path):
    import pytest

    from src.core.exception import CustomException
    from src.services import git_manager as git_module

    manager = _git_manager(monkeypatch, tmp_path)
    monkeypatch.setattr(
        _FakeRepo,
        "init",
        classmethod(lambda cls, path: _repo_with_git_error(cls, path, git_module, "commit")),
    )

    with pytest.raises(CustomException) as error:
        manager.init_local_repo_from_dir()

    assert error.value.status_code == 500


def _repo_with_git_error(cls, path, git_module, stage):
    repo = cls(path)
    repo.git = _FakeGit(errors={stage: git_module.GitCommandError(stage, 1)})
    return repo


def test_git_init_wraps_an_unusable_repository(monkeypatch, tmp_path):
    import pytest
    from git import GitCommandError

    from src.core.exception import CustomException

    manager = _git_manager(monkeypatch, tmp_path, errors={"init": GitCommandError("init", 1)})

    with pytest.raises(CustomException):
        manager.init_local_repo_from_dir()


def test_git_push_authenticates_with_the_injected_credentials(monkeypatch, tmp_path):
    manager = _git_manager(monkeypatch, tmp_path)

    manager.push_local_repo_to_remote_repo("http://gitea.local/git/websoft9/app.git", "git", "secret")

    repo = _FakeRepo.instances[0]
    assert repo.remotes == [("origin", "http://git:secret@gitea.local/git/websoft9/app.git")]
    assert repo.git.calls == [("push", ("origin", "HEAD:refs/heads/main"))]


def test_git_push_requires_an_existing_directory(monkeypatch, tmp_path):
    import pytest

    from src.core.exception import CustomException

    manager = _git_manager(monkeypatch, tmp_path / "missing")

    with pytest.raises(CustomException):
        manager.push_local_repo_to_remote_repo("http://gitea.local/app.git", "git", "secret")


def test_git_push_wraps_a_rejected_remote(monkeypatch, tmp_path):
    import pytest
    from git import GitCommandError

    from src.core.exception import CustomException

    manager = _git_manager(monkeypatch, tmp_path, errors={"remote": GitCommandError("remote", 1)})

    with pytest.raises(CustomException):
        manager.push_local_repo_to_remote_repo("http://gitea.local/app.git", "git", "secret")


def test_git_push_wraps_a_failed_push(monkeypatch, tmp_path):
    import pytest

    from src.core.exception import CustomException
    from src.services import git_manager as git_module

    manager = _git_manager(monkeypatch, tmp_path)

    def failing_push(self, *args):
        raise git_module.GitCommandError("push", 1)

    monkeypatch.setattr(_FakeGit, "push", failing_push)

    with pytest.raises(CustomException):
        manager.push_local_repo_to_remote_repo("http://gitea.local/app.git", "git", "secret")
    assert CustomException is not None


def test_git_clone_uses_the_authenticated_url(monkeypatch, tmp_path):
    manager = _git_manager(monkeypatch, tmp_path / "checkout")

    manager.clone_remote_repo_to_local("http://gitea.local/git/websoft9/app.git", "git", "secret")

    assert _FakeRepo.cloned == [("http://git:secret@gitea.local/git/websoft9/app.git", str(tmp_path / "checkout"))]


def test_git_clone_wraps_a_failure(monkeypatch, tmp_path):
    import pytest
    from git import GitCommandError

    from src.core.exception import CustomException

    manager = _git_manager(monkeypatch, tmp_path / "checkout", errors={"clone": GitCommandError("clone", 1)})

    with pytest.raises(CustomException):
        manager.clone_remote_repo_to_local("http://gitea.local/app.git", "git", "secret")


def test_git_manager_normalizes_the_clone_url(monkeypatch, tmp_path):
    from src.services import git_manager as git_module

    manager = _git_manager(monkeypatch, tmp_path)
    monkeypatch.setattr(git_module, "normalize_runtime_git_url", lambda url: url.replace("gitea.local", "127.0.0.1:3001"))

    manager.clone_remote_repo_to_local("http://gitea.local/git/websoft9/app.git", "git", "secret")

    # 归一化后的地址才是真正被使用的,凭据注入在其之上
    assert _FakeRepo.cloned[0][0] == "http://git:secret@127.0.0.1:3001/git/websoft9/app.git"
