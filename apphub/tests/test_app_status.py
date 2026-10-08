import sys
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.app_status import (
    add_installing_logs,
    appInstalling,
    appInstallingError,
    configure_install_state_store,
    get_app_custom_fields,
    modify_app_information,
    remove_app_installation,
    remove_installation_logs,
    save_app_custom_fields,
    begin_install_deploy,
    install_cancel_requested,
    mark_install_cancelled,
    request_install_cancel,
    set_install_phase,
    start_app_installation,
)


def test_install_tracking_persists_across_store_reconfigure(tmp_path):
    configure_install_state_store(str(tmp_path))

    tracking_id = start_app_installation("php_demo", "PHP", reserved_ports={9011})
    add_installing_logs(tracking_id, "Initializing installation", "")
    add_installing_logs(tracking_id, "Pulling docker image", {"status": "Pulling", "id": "sha256:demo"})

    configure_install_state_store(str(tmp_path))

    installing = dict(appInstalling.items())[tracking_id]
    assert installing["app_id"] == "php_demo"
    assert installing["reserved_ports"] == {9011}
    assert [stage["title"] for stage in installing["logs"]] == [
        "Initializing installation",
        "Pulling docker image",
    ]
    assert installing["logs"][1]["sub_logs"][0]["message"] == "Pulling #sha256:demo"


def test_error_transition_keeps_persisted_stage_logs(tmp_path):
    configure_install_state_store(str(tmp_path))

    tracking_id = start_app_installation("php_demo", "PHP")
    add_installing_logs(tracking_id, "Starting the services", "Booting containers")

    modify_app_information(tracking_id, "Portainer restarted during build")
    remove_installation_logs(tracking_id)

    assert tracking_id not in appInstalling
    errored = dict(appInstallingError.items())[tracking_id]
    assert errored["error"] == "Portainer restarted during build"
    assert errored["logs"][0]["title"] == "Starting the services"
    assert errored["logs"][0]["sub_logs"][0]["message"] == "Booting containers"


def test_image_layer_progress_updates_in_place_without_losing_other_layers(tmp_path):
    configure_install_state_store(str(tmp_path))
    tracking_id = start_app_installation("progress_demo", "Progress")
    for layer in range(25):
        add_installing_logs(tracking_id, "Pulling docker image", {"image": "mysql:8", "id": str(layer), "status": "Downloading", "progressDetail": {"current": 1, "total": 100}})
    for current in range(2, 101):
        add_installing_logs(tracking_id, "Pulling docker image", {"image": "mysql:8", "id": "0", "status": "Downloading", "progressDetail": {"current": current, "total": 100}})
    logs = dict(appInstalling.items())[tracking_id]["logs"][0]["sub_logs"]
    assert len(logs) == 25
    assert logs[0]["progressDetail"]["current"] == 100
    add_installing_logs(tracking_id, "Pulling docker image", {"image": "redis:7", "id": "0", "status": "Downloading"})
    assert len(dict(appInstalling.items())[tracking_id]["logs"][0]["sub_logs"]) == 26


def test_image_progress_does_not_overwrite_raw_error_records(tmp_path):
    configure_install_state_store(str(tmp_path))
    tracking_id = start_app_installation("progress_demo", "Progress")
    add_installing_logs(tracking_id, "Pulling docker image", {"image": "mysql:8", "id": "abc", "status": "error", "details": "timeout"})
    add_installing_logs(tracking_id, "Pulling docker image", {"image": "mysql:8", "id": "abc", "status": "Downloading"})
    logs = dict(appInstalling.items())[tracking_id]["logs"][0]["sub_logs"]
    assert len(logs) == 2
    assert logs[0]["details"] == "timeout"


def test_completion_log_is_written_before_installation_cleanup(tmp_path):
    configure_install_state_store(str(tmp_path))

    tracking_id = start_app_installation("php_demo", "PHP")
    add_installing_logs(tracking_id, "Installation complete", "")
    remove_app_installation(tracking_id)

    assert tracking_id not in appInstalling


def test_install_cancellation_is_only_accepted_while_pulling(tmp_path):
    configure_install_state_store(str(tmp_path))
    tracking_id = start_app_installation("php_demo", "PHP")

    assert request_install_cancel("php_demo") is None
    set_install_phase(tracking_id, "pulling")
    assert request_install_cancel("php_demo") == tracking_id
    assert install_cancel_requested(tracking_id) is True
    assert begin_install_deploy(tracking_id) is False

    mark_install_cancelled(tracking_id)
    assert tracking_id not in appInstalling


def test_custom_fields_persist_multiple_empty_rows(tmp_path):
    configure_install_state_store(str(tmp_path))

    saved = save_app_custom_fields("ghost", [
        {"field_name": "", "field_value": "", "field_type": "text"},
        {"field_name": "", "field_value": "", "field_type": "password"},
    ])

    assert [(field["field_name"], field["field_value"], field["field_type"]) for field in saved] == [
        ("", "", "text"),
        ("", "", "password"),
    ]

    configure_install_state_store(str(tmp_path))
    assert len(get_app_custom_fields("ghost")) == 2


def test_custom_fields_migrates_legacy_unique_constraint_safely(tmp_path):
    """Old table with UNIQUE(app_id, field_name) must be migrated without data loss."""
    database_file = tmp_path / "install-tracking.sqlite"
    with sqlite3.connect(database_file) as connection:
        connection.execute(
            """
            CREATE TABLE app_custom_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_value TEXT NOT NULL DEFAULT '',
                field_type TEXT NOT NULL DEFAULT 'text',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(app_id, field_name)
            )
            """
        )
        connection.execute(
            "INSERT INTO app_custom_fields (app_id, field_name, field_value, field_type, sort_order, created_at, updated_at) VALUES ('ghost', 'secret', 'oldvalue', 'password', 0, '2025-01-01', '2025-01-01')"
        )

    # Run migration by initialising the store against the legacy database.
    configure_install_state_store(str(tmp_path))

    # Legacy row must survive the migration.
    fields = get_app_custom_fields("ghost")
    assert len(fields) == 1
    assert fields[0]["field_name"] == "secret"
    assert fields[0]["field_value"] == "oldvalue"
    assert fields[0]["field_type"] == "password"

    # After migration, multiple empty-name rows must also be allowed.
    saved = save_app_custom_fields("ghost", [
        {"field_name": "", "field_value": "", "field_type": "text"},
        {"field_name": "", "field_value": "", "field_type": "text"},
    ])
    assert len(saved) == 2