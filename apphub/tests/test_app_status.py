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
    remove_installation_logs,
    save_app_custom_fields,
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


def test_custom_fields_rebuilds_legacy_unique_name_constraint(tmp_path):
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
            "INSERT INTO app_custom_fields (app_id, field_name, field_value, field_type, sort_order, created_at, updated_at) VALUES ('ghost', 'existing', '', 'text', 0, 'now', 'now')"
        )

    configure_install_state_store(str(tmp_path))
    assert get_app_custom_fields("ghost") == []

    saved = save_app_custom_fields("ghost", [
        {"field_name": "", "field_value": "", "field_type": "text"},
        {"field_name": "", "field_value": "", "field_type": "text"},
    ])

    assert len(saved) == 2