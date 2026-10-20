import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.git_url_resolver import normalize_runtime_git_url


def test_normalize_runtime_git_url_maps_legacy_gitea_host_in_single_container_runtime(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_RUNTIME_LAYOUT", "single-container-target")
    monkeypatch.setenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN", "http://47.239.243.133:9000")

    assert normalize_runtime_git_url("http://websoft9-git:3000/websoft9/moodle_ntg2o.git") == "http://127.0.0.1:3001/websoft9/moodle_ntg2o.git"


def test_normalize_runtime_git_url_strips_w9git_prefix_for_internal_clone(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_RUNTIME_LAYOUT", "single-container-target")
    monkeypatch.setenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN", "http://47.239.243.133:9000")

    assert normalize_runtime_git_url("http://127.0.0.1:9000/w9git/websoft9/moodle_ntg2o.git") == "http://127.0.0.1:3001/websoft9/moodle_ntg2o.git"


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
