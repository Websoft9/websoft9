from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner
from click.shell_completion import BashComplete


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli.apphub_cli import cli


def command_paths(group: click.Group, prefix: tuple[str, ...] = ()):
    yield prefix
    for name, command in group.commands.items():
        path = (*prefix, name)
        if isinstance(command, click.Group):
            yield from command_paths(command, path)
        else:
            yield path


@pytest.mark.parametrize("path", list(command_paths(cli)), ids=lambda path: " ".join(path) or "root")
def test_short_and_long_help_are_identical_at_every_level(path, tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "not-created"))
    runner = CliRunner()
    short = runner.invoke(cli, [*path, "-h"], prog_name="websoft9")
    long = runner.invoke(cli, [*path, "--help"], prog_name="websoft9")
    assert short.exit_code == long.exit_code == 0, short.output
    assert short.stdout == long.stdout
    assert "-h, --help" in short.stdout
    assert not (tmp_path / "not-created").exists()


def test_root_help_is_organized_and_no_arguments_show_help():
    runner = CliRunner()
    help_result = runner.invoke(cli, ["-h"], prog_name="websoft9")
    empty = runner.invoke(cli, [], prog_name="websoft9")
    assert help_result.exit_code == 0
    assert help_result.stderr == ""
    assert empty.exit_code == 2
    assert empty.output == help_result.stdout
    for title in ("Applications:", "Infrastructure:", "Platform:"):
        assert title in help_result.stdout
    for name in ("getconfig", "setconfig", "setsysconfig", "resetpwd", "images", "check-update", "log-cleanup", "upgrade"):
        assert f"  {name} " not in help_result.stdout
        assert name in cli.commands
    assert sum(not command.hidden for command in cli.commands.values()) == 11


@pytest.mark.parametrize("incomplete", ["", "get", "set", "im", "check-", "log-", "reset", "up", "missing", "--", "-h"])
def test_completion_preserves_legacy_entries_without_exposing_internal_commands(incomplete, tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "not-created"))
    with click.Context(cli) as ctx:
        results = cli.shell_complete(ctx, incomplete)
    names = [item.value for item in results]
    legacy = {"getconfig", "setconfig", "setsysconfig", "resetpwd", "images", "check-update", "log-cleanup", "upgrade"}
    assert legacy.intersection(names) == {name for name in legacy if name.startswith(incomplete)}
    assert len(names) == len(set(names))
    assert all(name.startswith(incomplete) for name in names)
    assert "setedition" not in names
    assert "reconcile-scheduled-tasks" not in names
    if incomplete == "":
        assert {name for name, command in cli.commands.items() if not command.hidden} <= set(names)
    if incomplete == "--":
        assert {"--help", "--version"} <= set(names)
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize(("args", "incomplete", "expected"), [
    (["images"], "", {"prewarm", "dispatch"}),
    (["images", "dispatch"], "--qui", {"--quiet"}),
    (["images", "prewarm"], "--app", {"--app"}),
    (["getconfig"], "--sec", {"--section"}),
    (["settings", "config", "get"], "--key", {"--key"}),
    (["app"], "data", {"database"}),
    (["app", "database"], "", {"list", "test"}),
    (["app", "database", "test"], "--pass", {"--password-stdin"}),
])
def test_completion_resolves_legacy_and_recommended_paths(args, incomplete, expected, tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "not-created"))
    completion = BashComplete(cli, {}, "websoft9", "_WEBSOFT9_COMPLETE")
    assert {item.value for item in completion.get_completions(args, incomplete)} == expected
    assert not (tmp_path / "not-created").exists()


def test_version_is_eager_and_uses_release_file(tmp_path, monkeypatch):
    from src.services import product_runtime_state

    version = tmp_path / "version.json"
    version.write_text('{"version":"2.4.4"}')
    monkeypatch.setattr(product_runtime_state, "VERSION_FILE", version)
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "not-created"))
    result = CliRunner().invoke(cli, ["--version"], prog_name="websoft9")
    assert result.exit_code == 0
    assert result.stdout == "websoft9, version 2.4.4\n"
    assert not (tmp_path / "not-created").exists()


def test_missing_version_reports_an_error(tmp_path, monkeypatch):
    from src.services import product_runtime_state

    monkeypatch.setattr(product_runtime_state, "VERSION_FILE", tmp_path / "absent.json")
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 1
    assert "version is unavailable" in result.output


@pytest.mark.parametrize(("path", "warning"), [
    (["settings", "config", "get"], "unmasked secrets"),
    (["settings", "upgrade", "check-and-prepare"], "not a read-only check"),
    (["app", "database"], "Websoft9's internal databases"),
    (["git"], "not a general-purpose Git client"),
    (["backup"], "not a platform-wide backup"),
    (["gateway"], "not the platform gateway process"),
    (["service"], "Application containers are managed with app"),
    (["host"], "not a general-purpose remote host"),
    (["host", "env-check"], "not a complete inspection of a remote host"),
])
def test_help_describes_sensitive_or_mutating_aliases(path, warning):
    result = CliRunner().invoke(cli, [*path, "-h"])
    assert result.exit_code == 0
    assert warning in " ".join(result.stdout.split())


def test_database_is_an_app_subgroup_without_an_unused_legacy_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "not-created"))
    assert "db" not in cli.commands
    assert "database" not in cli.commands
    assert set(cli.commands["app"].commands["database"].commands) == {"list", "test"}
    result = CliRunner().invoke(cli, ["db", "list"])
    assert result.exit_code == 2
    assert "No such command 'db'" in result.stderr
    with click.Context(cli) as ctx:
        names = {item.value for item in cli.shell_complete(ctx, "")}
    assert not {"db", "database"} & names
    assert not (tmp_path / "not-created").exists()


def test_app_database_test_preserves_stdin_and_masked_json(monkeypatch):
    from src.services import install_profile

    validator = Mock(return_value=Mock(version=(8, 0, 36), database_type="mysql"))
    monkeypatch.setattr(install_profile, "validate_external_database_connection", validator)
    args = [
        "app", "database", "test", "--type", "mysql", "--host", "db.example.test",
        "--port", "3306", "--database", "appdb", "--username", "appuser", "--json",
    ]
    runner = CliRunner()
    missing = runner.invoke(cli, args)
    assert missing.exit_code == 2
    assert json.loads(missing.stdout)["code"] == "INVALID_ARGUMENT"
    assert "app database test" in json.loads(missing.stdout)["error"]["message"]
    validator.assert_not_called()
    result = runner.invoke(cli, [*args, "--password-stdin"], input="fixture-secret\n")
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert "fixture-secret" not in result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["version"] == "8.0.36"
    validator.assert_called_once_with("mysql", "db.example.test", 3306, "appdb", "appuser", "fixture-secret")


@pytest.mark.parametrize(("canonical", "legacy"), [
    (("settings", "config", "get"), ("getconfig",)),
    (("settings", "config", "set"), ("setconfig",)),
    (("settings", "config", "set-system"), ("setsysconfig",)),
    (("settings", "auth", "reset-password"), ("resetpwd",)),
    (("settings", "upgrade", "check-and-prepare"), ("check-update",)),
    (("service", "cleanup-logs"), ("log-cleanup",)),
    (("appstore", "prewarm"), ("images", "prewarm")),
    (("task", "dispatch-prewarm"), ("images", "dispatch")),
])
def test_recommended_paths_reuse_legacy_callback_and_parameters(canonical, legacy):
    def resolve(path):
        command = cli
        for name in path:
            assert isinstance(command, click.Group)
            command = command.commands[name]
        return command

    old, new = resolve(legacy), resolve(canonical)
    assert old is not new
    assert old.callback is new.callback
    assert old.params == new.params
    assert new.hidden is False


def test_config_aliases_preserve_values_and_system_target(tmp_path, monkeypatch):
    config = tmp_path / "config.ini"
    system = tmp_path / "system.ini"
    config.write_text("[example]\nvalue = before\n")
    system.write_text("[example]\nvalue = system-before\n")
    monkeypatch.setenv("WEBSOFT9_APPHUB_CONFIG_PATH", str(config))
    monkeypatch.setenv("WEBSOFT9_APPHUB_SYSTEM_CONFIG_PATH", str(system))
    runner = CliRunner()
    for path in (["setconfig"], ["settings", "config", "set"]):
        result = runner.invoke(cli, [*path, "--section", "example", "--key", "value", "--value", "after"])
        assert result.exit_code == 0, result.output
        assert result.stdout == result.stderr == ""
    for path in (["getconfig"], ["settings", "config", "get"]):
        result = runner.invoke(cli, [*path, "--section", "example", "--key", "value"])
        assert result.exit_code == 0
        assert result.stdout == "after\n"
        assert result.stderr == ""
    for path in (["setsysconfig"], ["settings", "config", "set-system"]):
        result = runner.invoke(cli, [*path, "--section", "example", "--key", "value", "--value", "system-after"])
        assert result.exit_code == 0
        assert result.stdout == "Set [example] value=system-after in system.ini successfully.\n"
        assert result.stderr == ""
        assert "value = system-after" in system.read_text()
        assert "system-after" not in config.read_text()


@pytest.mark.parametrize("path", [["getconfig"], ["settings", "config", "get"]])
@pytest.mark.parametrize(("args", "expected"), [
    ([], {"api_key": {"key": "fixture-secret"}}),
    (["--section", "api_key"], {"key": "fixture-secret"}),
    (["--section", "api_key", "--key", "key"], "fixture-secret\n"),
])
def test_raw_config_output_remains_machine_readable(path, args, expected, tmp_path, monkeypatch):
    config = tmp_path / "config.ini"
    config.write_text("[api_key]\nkey = fixture-secret\n")
    monkeypatch.setenv("WEBSOFT9_APPHUB_CONFIG_PATH", str(config))
    result = CliRunner().invoke(cli, [*path, *args])
    assert result.exit_code == 0
    assert result.stderr == ""
    if isinstance(expected, dict):
        assert json.loads(result.stdout) == expected
    else:
        assert result.stdout == expected


def test_dispatch_alias_preserves_skip_exit_code_and_quiet(monkeypatch):
    from src.cli import apphub_cli

    service = Mock()
    service.dispatch_prewarm.return_value = {"status": "skipped"}
    monkeypatch.setattr(apphub_cli, "ScheduledTaskService", lambda: service)
    runner = CliRunner()
    for path in (["images", "dispatch"], ["task", "dispatch-prewarm"]):
        result = runner.invoke(cli, [*path, "--skip-if-running", "--quiet"])
        assert result.exit_code == 75
        assert result.stdout == result.stderr == ""


def test_alias_parameter_errors_preserve_json_envelope():
    result = CliRunner().invoke(cli, ["docker", "container", "logs", "fixture", "--tail", "0", "--json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["code"] == "INVALID_ARGUMENT"


def test_reorganized_reset_password_keeps_confirmation():
    result = CliRunner().invoke(cli, ["settings", "auth", "reset-password"], input="example\nexample\n")
    assert result.exit_code == 1
    assert "Password must be at least 8 characters" in result.output


@pytest.mark.parametrize("path", [["resetpwd"], ["settings", "auth", "reset-password"]])
@pytest.mark.parametrize("confirmed", [False, True])
def test_password_reset_keeps_final_confirmation_and_hidden_input(path, confirmed, monkeypatch):
    from src.cli import apphub_cli

    auth = Mock()
    auth.find_system_user.return_value = {"id": "fixture-user", "username": "fixture-admin"}
    monkeypatch.setattr(apphub_cli, "ProductAuthService", lambda: auth)
    password = "Fixture-pass9!"
    result = CliRunner().invoke(cli, path, input=f"{password}\n{password}\n{'y' if confirmed else 'n'}\n")
    assert result.exit_code == 0
    assert result.stderr == ""
    assert password not in result.stdout
    assert "Reset password for this user?" in result.stdout
    if confirmed:
        auth.reset_system_user_password.assert_called_once_with("fixture-user", password)
    else:
        auth.reset_system_user_password.assert_not_called()
        assert "Cancelled." in result.stdout
