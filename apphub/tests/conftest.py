import json
import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _isolate_appstore_runtime_state(tmp_path, monkeypatch):
    """Model a completed bootstrap without touching the machine's runtime marker."""
    state = tmp_path / "appstore-assets.json"
    state.write_text(json.dumps({"status": "ready", "datasetVersion": "unit-test-snapshot"}))
    monkeypatch.setenv("WEBSOFT9_APPSTORE_RUNTIME_STATE_FILE", str(state))


@pytest.fixture(autouse=True)
def _isolate_install_tracking_store(tmp_path):
    """Keep install tracking inside the test's own temporary directory.

    Install progress is stored in SQLite under ``WEBSOFT9_INSTALL_TRACKING_DIR``, which defaults to
    ``/opt/websoft9/data/config/apphub``. Tests that start an installation without pointing the
    store at a temporary directory therefore wrote to the real data root - and every later test in
    the same process saw those tasks, so a test expecting one application suddenly found two.
    """
    try:
        from src.services import app_status
    except Exception:  # pragma: no cover - a test may have replaced the package on purpose
        yield
        return

    configure = getattr(app_status, "configure_install_state_store", None)
    if configure is None:
        yield
        return

    previous = os.environ.get("WEBSOFT9_INSTALL_TRACKING_DIR")
    directory = str(tmp_path / "install-tracking")
    os.environ["WEBSOFT9_INSTALL_TRACKING_DIR"] = directory
    # `initialize=False` keeps the database from being created up front: readiness checks must keep
    # seeing an absent install-tracking database, exactly as on a fresh installation.
    configure(directory, initialize=False)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("WEBSOFT9_INSTALL_TRACKING_DIR", None)
        else:
            os.environ["WEBSOFT9_INSTALL_TRACKING_DIR"] = previous
        configure(previous, initialize=False)


@pytest.fixture(autouse=True, scope="session")
def _isolate_scheduled_task_cron_file():
    """Keep scheduled-task tests away from the real system crontab.

    Many tests build `ScheduledTaskService` with only `data_dir`, so the service fell back to its
    default `/etc/cron.d/websoft9-tasks`. Running the suite therefore overwrote the crontab of the
    machine it ran on -- and restarted that machine's cron -- with entries pointing at pytest
    temporary directories. The service already honours this environment variable, so pointing it at
    a throwaway directory keeps every test isolated without touching each call site.
    """
    previous = os.environ.get("WEBSOFT9_SCHEDULED_TASKS_CRON_FILE")
    with tempfile.TemporaryDirectory(prefix="w9-test-cron-") as directory:
        os.environ["WEBSOFT9_SCHEDULED_TASKS_CRON_FILE"] = os.path.join(directory, "websoft9-tasks")
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("WEBSOFT9_SCHEDULED_TASKS_CRON_FILE", None)
            else:
                os.environ["WEBSOFT9_SCHEDULED_TASKS_CRON_FILE"] = previous
