import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.git_manager import GitManager


def test_normalize_clone_url_maps_legacy_gitea_host_in_single_container_runtime(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_RUNTIME_LAYOUT", "single-container-target")
    monkeypatch.setenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN", "http://47.239.243.133:9000")

    manager = GitManager("/tmp/unused")

    assert manager._normalize_clone_url("http://websoft9-git:3000/websoft9/moodle_ntg2o.git") == "http://127.0.0.1:3001/websoft9/moodle_ntg2o.git"


def test_normalize_clone_url_strips_w9git_prefix_for_internal_clone(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_RUNTIME_LAYOUT", "single-container-target")
    monkeypatch.setenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN", "http://47.239.243.133:9000")

    manager = GitManager("/tmp/unused")

    assert manager._normalize_clone_url("http://127.0.0.1:9000/w9git/websoft9/moodle_ntg2o.git") == "http://127.0.0.1:3001/websoft9/moodle_ntg2o.git"