import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.app_status import (
    add_installing_logs,
    appInstalling,
    appInstallingError,
    configure_install_state_store,
    modify_app_information,
    remove_installation_logs,
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