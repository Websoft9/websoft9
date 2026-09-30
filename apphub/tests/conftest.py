import os
import tempfile

import pytest


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
