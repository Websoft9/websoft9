from __future__ import annotations

import base64
import json
import subprocess
import sys
import types
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from click.testing import CliRunner
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.env_file import parse_env_values


def response(payload=None, status=200, text=None):
    result = requests.Response()
    result.status_code = status
    result._content = (json.dumps(payload) if text is None else text).encode()
    return result


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Regression tests must not contact real services")

    monkeypatch.setattr(requests.sessions.Session, "request", fail)


@pytest.fixture(scope="module")
def gitpython():
    # Legacy suites install a collection-time stub; isolate it from real-repo tests.
    with pytest.MonkeyPatch.context() as patch:
        existing = sys.modules.get("git")
        if existing is not None and not hasattr(existing, "__path__"):
            patch.delitem(sys.modules, "git")
        import git

        yield git


@pytest.fixture
def manager(monkeypatch, gitpython):
    from src.core.apiHelper import APIHelper
    from src.external.gitea_api import GiteaAPI
    from src.services.gitea_manager import GiteaManager
    from src.services import gitea_manager

    monkeypatch.setattr(gitea_manager, "Repo", gitpython.Repo)

    api = GiteaAPI.__new__(GiteaAPI)
    api.owner = "fixture"
    api.api = APIHelper("https://gitea.invalid/api/v1", {"Authorization": "Basic fixture"})
    instance = GiteaManager.__new__(GiteaManager)
    instance.gitea = api
    return instance


@pytest.fixture
def env_file(monkeypatch):
    state = {"content": "KEY=old\n", "sha": "old-blob", "writes": []}

    def get(url, **kwargs):
        assert url.endswith("/repos/fixture/fixture/contents/.env")
        return response({
            "name": ".env",
            "encoding": "base64",
            "sha": state["sha"],
            "content": base64.b64encode(state["content"].encode()).decode(),
        })

    def put(url, **kwargs):
        assert url.endswith("/repos/fixture/fixture/contents/.env")
        payload = kwargs["json"]
        state["writes"].append(payload)
        state["written"] = base64.b64decode(payload["content"]).decode()
        return response({"content": {"sha": "new-blob"}, "commit": {"sha": "new-head"}})

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "put", put)
    return state


@pytest.mark.parametrize("value", [
    "abc #def",
    " leading and trailing ",
    r"C:\path\\",
    "both 'single' and \"double\" quotes",
    "line one\nline two",
    "line one\r\nline two",
    "${UNSET_VARIABLE}",
    "",
    "中文",
])
def test_env_set_round_trips_literal_values_and_blob_sha(manager, env_file, value):
    result = manager.update_env_variables("fixture", {"KEY": value}, expected_sha="old-blob")

    assert parse_env_values(env_file["written"])["KEY"] == value
    assert env_file["writes"][0]["sha"] == "old-blob"
    assert env_file["writes"][0]["branch"] == "main"
    assert result == {
        "path": ".env", "sha": "new-blob", "head_sha": "new-head", "updated_keys": ["KEY"],
    }


def test_env_set_updates_all_duplicates_and_preserves_unrelated_multiline_values(manager, env_file):
    preserved = "# keep comment\nUNTOUCHED='one\nKEY=not-an-assignment\nthree'\n"
    env_file["content"] = preserved + "\n export KEY=first\nKEY=last\nTAIL=no-newline"

    result = manager.update_env_variables("fixture", {"KEY": "new #literal", "ADDED": "new"})

    written = env_file["written"]
    assert written.startswith(preserved + '\n export KEY="new #literal"\n')
    assert written.count('KEY="new #literal"') == 2
    assert 'TAIL=no-newline\nADDED="new"\n' in written
    assert dotenv_values(stream=StringIO(written), interpolate=False)["KEY"] == "new #literal"
    assert result["updated_keys"] == ["KEY", "ADDED"]


def test_env_set_replaces_complete_multiline_assignment(manager, env_file):
    env_file["content"] = "KEY='first\nsecond'\nOTHER=kept\n"
    manager.update_env_variables("fixture", {"KEY": "replacement"})
    assert env_file["written"] == 'KEY="replacement"\nOTHER=kept\n'


def test_env_set_rejects_stale_sha_without_writing(manager, env_file):
    from src.core.exception import CustomException

    with pytest.raises(CustomException) as error:
        manager.update_env_variables("fixture", {"KEY": "new"}, expected_sha="stale-blob")
    assert error.value.status_code == 409
    assert env_file["writes"] == []


@pytest.mark.parametrize("key", ["", "A\nINJECTED", "A=B", "export A"])
def test_env_set_rejects_invalid_keys_before_reading(manager, key):
    from src.core.exception import CustomException

    with pytest.raises(CustomException) as error:
        manager.update_env_variables("fixture", {key: "value"})
    assert error.value.status_code == 400


def test_delete_uses_actual_helper_json_body_and_preserves_positional_headers(manager, monkeypatch):
    calls = []

    def delete(url, **kwargs):
        calls.append((url, kwargs))
        return response({"commit": {"sha": "delete-head"}})

    monkeypatch.setattr(requests, "delete", delete)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response({
        "name": "extra.conf", "encoding": "base64", "sha": "current-blob", "content": "",
    }))

    assert manager.delete_repo_file("fixture", "extra.conf", sha="current-blob") == {
        "path": "extra.conf", "deleted_sha": "current-blob", "head_sha": "delete-head",
    }
    assert calls[0][0].endswith("/repos/fixture/fixture/contents/extra.conf")
    assert calls[0][1]["json"] == {
        "branch": "main", "sha": "current-blob", "message": "Delete extra.conf",
    }
    manager.gitea.api.delete("legacy", {"force": True}, {"X-Legacy": "kept"})
    assert calls[1][1]["params"] == {"force": True}
    assert calls[1][1]["headers"] == {"Authorization": "Basic fixture", "X-Legacy": "kept"}
    assert calls[1][1]["json"] is None


def test_commit_diff_uses_raw_api_endpoint_and_returns_patch(manager, monkeypatch):
    patch = "diff --git a/config b/config\n--- a/config\n+++ b/config\n@@ -1 +1 @@\n-old\n+new\n"
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return response(text=patch)

    monkeypatch.setattr(requests, "get", get)
    assert manager.get_repo_diff("fixture", target_ref="feature/config")["diff"] == patch
    assert calls[0][0].endswith("/git/commits/feature%2Fconfig.diff")
    assert calls[0][1]["headers"]["Accept"] == "text/plain"


def git_dir(path, *args):
    return subprocess.check_output(["git", f"--git-dir={path}", *args], text=True).strip()


@pytest.fixture
def compose_update(local_repository, monkeypatch, tmp_path, gitpython):
    from src.services import compose_app_manager

    repository = local_repository()
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "missing-global-config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    portainer = Mock()
    portainer.get_local_endpoint_id.return_value = 7
    portainer.get_stack_by_name.return_value = {
        "Id": 9, "GitConfig": {"URL": str(repository.remote)},
    }
    credentials = SimpleNamespace(username="fixture", password="unused", email="fixture@example.invalid")
    monkeypatch.setattr(compose_app_manager, "Repo", gitpython.Repo)
    monkeypatch.setattr(compose_app_manager, "Actor", gitpython.Actor)
    monkeypatch.setattr(compose_app_manager, "PortainerManager", lambda: portainer)
    monkeypatch.setattr(compose_app_manager, "GiteaManager", Mock)
    monkeypatch.setattr(compose_app_manager, "_require_compose_app", Mock())
    monkeypatch.setattr(compose_app_manager, "IntegrationCredentialProvider", lambda: SimpleNamespace(
        get_gitea_credentials=lambda: credentials,
    ))
    service = compose_app_manager.ComposeAppManager()
    monkeypatch.setattr(service, "_pull_stack_images", Mock(return_value=[]))
    return SimpleNamespace(service=service, portainer=portainer, remote=repository.remote)


def test_compose_update_commits_without_global_identity_and_noop_redeploys(compose_update):
    content = "services:\n  worker:\n    image: fixture:latest\n"
    env = [{"key": "VALUE", "value": "updated"}]
    compose_update.service.update_compose_content("fixture", content, env, [])
    assert git_dir(compose_update.remote, "show", "main:docker-compose.yml") == content.strip()
    assert git_dir(compose_update.remote, "show", "main:.env") == 'VALUE="updated"'
    assert git_dir(compose_update.remote, "show", "-s", "--format=%an/%ae", "main") == "fixture/fixture@example.invalid"
    head = git_dir(compose_update.remote, "rev-parse", "main")
    compose_update.service.update_compose_content("fixture", content, env, [])
    assert git_dir(compose_update.remote, "rev-parse", "main") == head
    assert compose_update.portainer.redeploy_stack.call_count == 2


@pytest.mark.parametrize("value", [
    "", "$cash #hash spaces\\tail", "${HOME}", "it's \"quoted\"",
    " leading and trailing ", "first\nsecond", "first\r\nsecond",
    "path\\with\\slashes", "trailing\\",
])
def test_compose_env_round_trip_preserves_literals(compose_update, value):
    from src.schemas.appComposeInstall import ComposeEnvironmentEntry
    from src.services.compose_app_manager import _parse_user_env

    entry = ComposeEnvironmentEntry(key="VALUE", value=value)
    assert entry.value == value
    env = [{"key": entry.key, "value": entry.value}]
    compose_update.service.update_compose_content(
        "fixture", "services:\n  worker:\n    image: fixture:latest\n", env, [],
    )
    content = git_dir(compose_update.remote, "show", "main:.env")
    assert _parse_user_env(content) == env


def test_compose_env_parser_preserves_single_quoted_backslashes_and_filters_platform_keys():
    from src.services.compose_app_manager import _parse_user_env

    assert _parse_user_env("VALUE='two\\\\slashes'\nW9_INTERNAL=hidden\nUNSET\n") == [
        {"key": "VALUE", "value": "two\\\\slashes"},
    ]


def test_compose_env_parser_rejects_invalid_assignment_without_echoing_value():
    from src.core.exception import CustomException

    with pytest.raises(CustomException) as caught:
        parse_env_values('VALUE="fixture-secret-without-closing-quote\n')
    assert caught.value.status_code == 400
    assert "fixture-secret" not in caught.value.details


@pytest.mark.parametrize("failure", ["commit", "push"])
def test_compose_update_failure_never_redeploys(compose_update, monkeypatch, gitpython, failure):
    from src.core.exception import CustomException

    head = git_dir(compose_update.remote, "rev-parse", "main")
    if failure == "commit":
        def fail_commit(*args, **kwargs):
            raise gitpython.GitCommandError("git commit", 128, stderr="fixture commit rejected")
        monkeypatch.setattr(gitpython.IndexFile, "commit", fail_commit)
    else:
        hook = compose_update.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
    with pytest.raises(CustomException) as caught:
        compose_update.service.update_compose_content(
            "fixture", "services:\n  worker:\n    image: fixture:latest\n", [], [],
        )
    assert caught.value.status_code == 500
    assert git_dir(compose_update.remote, "rev-parse", "main") == head
    compose_update.portainer.redeploy_stack.assert_not_called()


@pytest.fixture
def local_repository(manager, monkeypatch, tmp_path, gitpython):
    from src.services import gitea_manager
    from src.services.git_manager import GitManager

    source = gitpython.Repo.init(tmp_path / "source", initial_branch="main")
    with source.config_writer() as writer:
        writer.set_value("user", "name", "Fixture").set_value("user", "email", "fixture@example.invalid")
    work = Path(source.working_tree_dir)
    (work / "config").write_text("old\n")
    (work / "removed").write_text("restore me\n")
    (work / "script").write_text("#!/bin/sh\nexit 0\n")
    (work / "script").chmod(0o755)
    (work / "link").symlink_to("config")
    source.git.add(A=True)
    target = source.index.commit("target")

    def prepare(*, additions_only=False, reject=False, other_default=False):
        (work / "added").write_text("must disappear on rollback\n")
        if not additions_only:
            (work / "config").write_text("new\n")
            (work / "removed").unlink()
            (work / "script").chmod(0o644)
            (work / "link").unlink()
            (work / "link").symlink_to("added")
        source.git.add(A=True)
        previous = source.index.commit("later")
        if other_default:
            source.git.checkout("-b", "other")
            (work / "other").write_text("not main\n")
            source.git.add(A=True)
            source.index.commit("other branch")
        remote = tmp_path / "remote.git"
        gitpython.Repo.clone_from(str(work), remote, bare=True).close()
        if reject:
            hook = remote / "hooks" / "pre-receive"
            hook.write_text("#!/bin/sh\nexit 1\n")
            hook.chmod(0o755)
        monkeypatch.setattr(requests, "get", lambda *a, **kw: response({"clone_url": str(remote)}))
        return SimpleNamespace(remote=remote, target=target.hexsha, previous=previous.hexsha)

    def local_clone(self, remote_url, username, password):
        assert username == "fixture" and password == "unused"
        gitpython.Repo.clone_from(remote_url, self.local_path).close()

    monkeypatch.setattr(GitManager, "clone_remote_repo_to_local", local_clone)
    monkeypatch.setattr(gitea_manager, "IntegrationCredentialProvider", lambda: SimpleNamespace(
        get_gitea_credentials=lambda: SimpleNamespace(
            username="fixture", password="unused", email="fixture@example.invalid",
        ),
    ))
    monkeypatch.setattr(gitea_manager.tempfile, "tempdir", str(tmp_path))
    yield prepare
    source.close()


@pytest.mark.parametrize("additions_only,other_default", [(True, False), (False, False), (False, True)])
def test_rollback_restores_exact_tree_with_new_commit_preserving_main_history(
    manager, local_repository, additions_only, other_default,
):
    fixture = local_repository(additions_only=additions_only, other_default=other_default)
    result = manager.rollback_repo_to_commit("fixture", fixture.target)

    assert result["changed"] is True
    assert result["previous_head_sha"] == fixture.previous
    assert result["new_head_sha"] == git_dir(fixture.remote, "rev-parse", "main")
    assert git_dir(fixture.remote, "rev-parse", "main^") == fixture.previous
    assert git_dir(fixture.remote, "rev-parse", "main^{tree}") == git_dir(
        fixture.remote, "rev-parse", fixture.target + "^{tree}",
    )
    assert "added" not in git_dir(fixture.remote, "ls-tree", "-r", "--name-only", "main").splitlines()


def test_rollback_current_head_is_noop(manager, local_repository):
    fixture = local_repository()
    result = manager.rollback_repo_to_commit("fixture", fixture.previous)
    assert result["changed"] is False
    assert git_dir(fixture.remote, "rev-parse", "main") == fixture.previous


def test_rollback_rejected_by_real_hook_raises_and_keeps_remote_unchanged(manager, local_repository):
    from src.core.exception import CustomException

    fixture = local_repository(reject=True)
    with pytest.raises(CustomException) as error:
        manager.rollback_repo_to_commit("fixture", fixture.target)
    assert error.value.status_code == 502
    assert git_dir(fixture.remote, "rev-parse", "main") == fixture.previous


@pytest.mark.parametrize("failure", ["empty", "flags", "exception"])
def test_rollback_checks_all_push_failure_results(manager, local_repository, monkeypatch, gitpython, failure):
    from git.remote import PushInfo, PushInfoList, Remote
    from src.core.exception import CustomException

    fixture = local_repository()

    def fail_push(self, *args, **kwargs):
        if failure == "exception":
            raise gitpython.GitCommandError("git push", 128, stderr="fixture transport failure")
        result = PushInfoList()
        if failure == "flags":
            result.append(PushInfo(PushInfo.ERROR | PushInfo.REJECTED, None, "refs/heads/main", self))
        return result

    monkeypatch.setattr(Remote, "push", fail_push)
    with pytest.raises(CustomException) as error:
        manager.rollback_repo_to_commit("fixture", fixture.target)
    assert error.value.status_code == 502
    assert git_dir(fixture.remote, "rev-parse", "main") == fixture.previous


def test_failed_rollback_never_redeploys_from_cli(manager, local_repository, monkeypatch):
    from src.cli.git_commands import git_group
    from src.services import gitea_manager

    fixture = local_repository(reject=True)
    redeploy_calls = []

    class ForbiddenRedeploy:
        def __init__(self):
            redeploy_calls.append("called")
            raise AssertionError("Failed rollback must not redeploy")

    for module_name, class_name in [
        ("src.services.app_manager", "AppManger"),
        ("src.services.compose_app_manager", "ComposeAppManager"),
    ]:
        module = types.ModuleType(module_name)
        setattr(module, class_name, ForbiddenRedeploy)
        monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setattr(gitea_manager, "GiteaManager", lambda: manager)

    result = CliRunner().invoke(git_group, [
        "rollback", "fixture", "--to", fixture.target, "--redeploy", "--yes", "--json",
    ])
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["ok"] is False
    assert redeploy_calls == []
    assert git_dir(fixture.remote, "rev-parse", "main") == fixture.previous


@pytest.mark.parametrize("default_target", [False, True])
def test_range_diff_is_real_tree_patch_including_additions_and_deletions(
    manager, local_repository, default_target,
):
    fixture = local_repository()
    result = manager.get_repo_diff(
        "fixture", target_ref=None if default_target else fixture.previous, base_ref=fixture.target,
    )
    expected = git_dir(
        fixture.remote, "diff", "--no-ext-diff", "--no-textconv", fixture.target, fixture.previous, "--",
    )
    assert result["diff"] == expected
    assert "diff --git" in result["diff"]
    assert "new file mode" in result["diff"]
    assert "deleted file mode" in result["diff"]
    assert "-old\n+new" in result["diff"]
    assert result["target"] == fixture.previous


def test_range_diff_invalid_ref_fails_instead_of_returning_single_commit(manager, local_repository):
    from src.core.exception import CustomException

    fixture = local_repository()
    with pytest.raises(CustomException) as error:
        manager.get_repo_diff("fixture", target_ref=fixture.previous, base_ref="missing-ref")
    assert error.value.status_code == 404
