from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from click.testing import CliRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_service_list_and_logs_and_runtime_logs_cli(monkeypatch, tmp_path):
    from src.cli.service_commands import service_group
    from src.services.core_services import CoreServicesService, HealthProbeResult, ServiceDefinition
    from src.services.runtime_logs import RuntimeLogsService

    gw_log = tmp_path / "platform-gateway-error.log"
    gw_log.write_text(
        "2026-10-20T08:00:00Z ERROR upstream connection failed password=topsecret\n",
        encoding="utf-8",
    )
    definitions = [
        ServiceDefinition(
            key="platform-gateway",
            label="Platform Gateway",
            description="Gateway",
            supervisor_program="platform-gateway",
            health_url="http://127.0.0.1:9000/w9gateway/healthz",
            log_root=tmp_path,
            log_paths=(gw_log,),
        )
    ]

    monkeypatch.setattr(
        CoreServicesService,
        "__init__",
        lambda self, **kwargs: (
            setattr(self, "auth_service", None),
            setattr(self, "service_definitions", tuple(definitions)),
            setattr(self, "_supervisor_status_loader", lambda: {"platform-gateway": "RUNNING"}),
            setattr(self, "_health_probe", lambda d: HealthProbeResult(ok=True, detail="HTTP 200")),
            setattr(self, "_now_provider", lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
        ) and None,
    )

    runtime_log = tmp_path / "platform-runtime.log"
    runtime_log.write_text(
        json.dumps(
            {
                "timestamp": "2026-10-20T08:01:00Z",
                "level": "error",
                "component": "platform-gateway",
                "message": "Gateway token=secret123456 failed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH", str(runtime_log))
    monkeypatch.setattr(
        RuntimeLogsService,
        "__init__",
        lambda self, **kwargs: (
            setattr(self, "auth_service", None),
            setattr(self, "log_path", runtime_log),
            setattr(self, "excluded_components", {"apphub-api"}),
        ) and None,
    )

    runner = CliRunner()
    list_res = runner.invoke(service_group, ["list", "--json"])
    assert list_res.exit_code == 0, list_res.output
    list_payload = json.loads(list_res.output)
    assert list_payload["ok"] is True
    assert list_payload["data"]["services"][0]["key"] == "platform-gateway"
    assert list_payload["data"]["services"][0]["health_state"] == "healthy"

    logs_res = runner.invoke(service_group, ["logs", "platform-gateway", "--level", "error", "--json"])
    assert logs_res.exit_code == 0, logs_res.output
    logs_payload = json.loads(logs_res.output)
    assert logs_payload["ok"] is True
    assert len(logs_payload["data"]["entries"]) == 1
    assert "topsecret" not in logs_payload["data"]["entries"][0]["message"]

    rt_res = runner.invoke(service_group, ["runtime-logs", "--level", "error", "--json"])
    assert rt_res.exit_code == 0, rt_res.output
    rt_payload = json.loads(rt_res.output)
    assert rt_payload["ok"] is True
    assert len(rt_payload["data"]["entries"]) == 1
    assert "secret123456" not in rt_payload["data"]["entries"][0]["message"]


def test_app_validate_and_install_compose_cli(monkeypatch, tmp_path):
    from src.cli.app_commands import app_group

    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        "services:\n  web:\n    image: nginx:alpine\n    ports:\n      - '8080:80'\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    val_res = runner.invoke(
        app_group,
        ["validate-compose", "--file", str(compose_file), "--app-id", "mycompose", "--env", "FOO=bar", "--json"],
    )
    assert val_res.exit_code == 0, val_res.output
    val_payload = json.loads(val_res.output)
    assert val_payload["ok"] is True
    assert val_payload["data"]["valid"] is True
    assert val_payload["data"]["services"] == ["web"]

    # Without --yes in --json mode, install-compose must require confirmation
    no_yes = runner.invoke(
        app_group,
        ["install-compose", "--app-id", "mycompose", "--file", str(compose_file), "--json"],
    )
    assert no_yes.exit_code == 1
    assert json.loads(no_yes.output)["code"] == "CONFIRMATION_REQUIRED"

    calls = []
    monkeypatch.setattr(
        "src.services.compose_install.prepare_compose_install_tracking",
        lambda payload: ("mycompose_1a2b3", "track-compose-1"),
    )
    monkeypatch.setattr(
        "src.services.compose_install.install_compose_application",
        lambda payload, endpoint_id, tracked_app_id, tracking_id: calls.append((tracked_app_id, tracking_id)),
    )

    inst_res = runner.invoke(
        app_group,
        ["install-compose", "--app-id", "mycompose", "--file", str(compose_file), "--yes", "--json"],
    )
    assert inst_res.exit_code == 0, inst_res.output
    inst_payload = json.loads(inst_res.output)
    assert inst_payload["data"]["app_id"] == "mycompose_1a2b3"
    assert calls == [("mycompose_1a2b3", "track-compose-1")]


def test_git_commands_masking_and_sha_conflict(monkeypatch, tmp_path):
    from src.cli.git_commands import git_group

    class FakeGiteaManager:
        def list_repos(self):
            return [{"name": "wp_123", "full_name": "w9/wp_123", "default_branch": "main", "empty": False, "updated_at": "2026-01-01T00:00:00Z"}]

        def list_repo_files(self, repo_name, dir_path=""):
            return {"head_sha": "head111", "current_dir": dir_path, "files": [{"path": ".env", "name": ".env", "type": "file", "size": 32, "sha": "sha-env-1"}]}

        def read_repo_text_file(self, repo_name, file_path):
            return {"path": file_path, "name": file_path, "sha": "sha-env-1", "content": "W9_APP_NAME=wordpress\nDB_PASSWORD=mysecret\n"}

        def update_env_variables(self, repo_name, updates, *, expected_sha=None):
            return {"path": ".env", "sha": "sha-env-2", "head_sha": "head222", "updated_keys": sorted(updates.keys())}

        def get_file_content_from_repo(self, repo_name, file_path):
            return {"name": file_path, "sha": "sha-compose-1", "content": ""}

        def write_repo_text_file(self, repo_name, file_path, content, sha=None):
            return {"path": file_path, "sha": "sha-compose-2", "head_sha": "head333"}

    gm_mod = types.ModuleType("src.services.gitea_manager")
    gm_mod.GiteaManager = FakeGiteaManager
    monkeypatch.setitem(sys.modules, "src.services.gitea_manager", gm_mod)

    runner = CliRunner()
    cat_res = runner.invoke(git_group, ["cat", "wp_123", ".env", "--json"])
    assert cat_res.exit_code == 0
    cat_payload = json.loads(cat_res.output)
    assert "mysecret" not in cat_payload["data"]["content"]
    assert "******" in cat_payload["data"]["content"]

    # Reject writing masked placeholder ******
    bad_env = runner.invoke(git_group, ["env-set", "wp_123", "--set", "DB_PASSWORD=******", "--yes", "--json"])
    assert bad_env.exit_code == 2
    assert json.loads(bad_env.output)["code"] == "INVALID_ARGUMENT"

    ok_env = runner.invoke(git_group, ["env-set", "wp_123", "--set", "W9_HTTP_PORT_SET=9080", "--sha", "sha-env-1", "--yes", "--json"])
    assert ok_env.exit_code == 0, ok_env.output
    assert json.loads(ok_env.output)["data"]["updated_keys"] == ["W9_HTTP_PORT_SET"]

    new_file = tmp_path / "docker-compose.yml"
    new_file.write_text("services:\n  app:\n    image: nginx:alpine\n", encoding="utf-8")

    # SHA mismatch conflict
    conflict_res = runner.invoke(
        git_group,
        ["write", "wp_123", "docker-compose.yml", "--from-file", str(new_file), "--sha", "wrong-sha", "--yes", "--json"],
    )
    assert conflict_res.exit_code == 1
    assert json.loads(conflict_res.output)["ok"] is False

    write_res = runner.invoke(
        git_group,
        ["write", "wp_123", "docker-compose.yml", "--from-file", str(new_file), "--sha", "sha-compose-1", "--yes", "--json"],
    )
    assert write_res.exit_code == 0, write_res.output
    assert json.loads(write_res.output)["data"]["sha"] == "sha-compose-2"


def test_db_gateway_backup_task_and_settings_cli(monkeypatch):
    from src.cli.backup_commands import backup_group
    from src.cli.apphub_cli import cli
    from src.cli.gateway_commands import gateway_group
    from src.cli.settings_commands import settings_group
    from src.cli.task_commands import task_group

    # 1. Application database connections
    app_mgr_mod = types.ModuleType("src.services.app_manager")

    class FakeAppManger:
        def get_external_databases(self, endpoint_id=None, locale="en", *, readonly=False):
            assert readonly is True
            return [
                {
                    "type": "mysql",
                    "address": "10.0.0.5:3306",
                    "database_name": "wpdb",
                    "username": "wpuser",
                    "password": "hiddenpassword",
                    "apps": [{"app_id": "wp_1", "app_name": "wordpress", "status": 1}],
                }
            ]

    app_mgr_mod.AppManger = FakeAppManger
    monkeypatch.setitem(sys.modules, "src.services.app_manager", app_mgr_mod)

    runner = CliRunner()
    db_list = runner.invoke(cli, ["app", "database", "list", "--json"])
    assert db_list.exit_code == 0
    assert "hiddenpassword" not in db_list.output
    assert json.loads(db_list.output)["data"]["items"][0]["has_password"] is True

    # 2. gateway cert list
    pm_mod = types.ModuleType("src.services.proxy_manager")

    class FakeProxyManager:
        def get_all_certificates(self):
            return [{"id": 3, "nice_name": "example.com", "provider": "letsencrypt", "domain_names": ["example.com"], "expires_on": "2027-01-01"}]

        def get_proxy_hosts(self):
            return [{"id": 1, "domain_names": ["example.com"], "forward_scheme": "http", "forward_host": "wp_1", "forward_port": 80, "certificate_id": 3, "ssl_forced": True, "enabled": True}]

    pm_mod.ProxyManager = FakeProxyManager
    monkeypatch.setitem(sys.modules, "src.services.proxy_manager", pm_mod)

    gw_list = runner.invoke(gateway_group, ["proxy", "list", "--json"])
    assert gw_list.exit_code == 0
    assert json.loads(gw_list.output)["data"]["total"] == 1

    cert_list = runner.invoke(gateway_group, ["cert", "list", "--json"])
    assert cert_list.exit_code == 0
    assert json.loads(cert_list.output)["data"]["items"][0]["nice_name"] == "example.com"

    # 3. backup list/create/delete
    bm_mod = types.ModuleType("src.services.back_manager")

    class FakeBackupManager:
        def list_snapshots(self, app_id=None, use_cache=True):
            return [{"id": "full123456", "short_id": "full1234", "time": "2026-10-20T00:00:00Z", "tags": [app_id or "wp_1"], "paths": ["/wp_data"], "hostname": "host1"}]

        def create_backup(self, app_id):
            return None

        def delete_snapshot(self, snapshot_id):
            return None

    bm_mod.BackupManager = FakeBackupManager
    monkeypatch.setitem(sys.modules, "src.services.back_manager", bm_mod)

    bk_list = runner.invoke(backup_group, ["list", "--app-id", "wp_1", "--json"])
    assert bk_list.exit_code == 0
    assert json.loads(bk_list.output)["data"]["items"][0]["id"] == "full1234"

    bk_create = runner.invoke(backup_group, ["create", "wp_1", "--yes", "--json"])
    assert bk_create.exit_code == 0
    assert json.loads(bk_create.output)["data"]["status"] == "created"

    # 4. task list & prewarm-records
    st_mod = types.ModuleType("src.services.scheduled_tasks")

    class FakeScheduledTaskService:
        def collect_tasks_local(self):
            return {
                "system_tasks": [{"task_id": "system:log-cleanup", "name": "Clean platform logs", "schedule": "0 4 * * 0", "enabled": True, "last_status": "success"}],
                "tasks": [],
                "prewarm_records": [{"task_id": "pw-1", "subject_app": "wordpress", "subject_version": "latest", "queue_state": "success", "last_status": "success"}],
            }

    st_mod.ScheduledTaskService = FakeScheduledTaskService
    monkeypatch.setitem(sys.modules, "src.services.scheduled_tasks", st_mod)

    tk_list = runner.invoke(task_group, ["list", "--json"])
    assert tk_list.exit_code == 0
    assert json.loads(tk_list.output)["data"]["system_tasks"][0]["task_id"] == "system:log-cleanup"

    pw_list = runner.invoke(task_group, ["prewarm-records", "list", "--json"])
    assert pw_list.exit_code == 0
    assert json.loads(pw_list.output)["data"]["items"][0]["subject_app"] == "wordpress"

    # 5. settings smtp get
    smtp_mod = types.ModuleType("src.services.smtp_service")

    class FakeSmtpService:
        def get_masked_settings(self):
            return {"enabled": True, "host": "smtp.example.com", "port": 587, "encryption": "starttls", "username": "mailer", "password_set": True, "from_email": "noreply@example.com", "from_name": "Websoft9"}

    smtp_mod.SmtpService = FakeSmtpService
    monkeypatch.setitem(sys.modules, "src.services.smtp_service", smtp_mod)

    smtp_res = runner.invoke(settings_group, ["smtp", "get", "--json"])
    assert smtp_res.exit_code == 0
    assert json.loads(smtp_res.output)["data"]["password_set"] is True
