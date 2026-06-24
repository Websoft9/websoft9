import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.portainer_manager import PortainerManager


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakePortainerApi:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create_stack_standlone_repository(self, stack_name, endpoint_id, repository_url, user_name, user_password):
        self.calls.append((stack_name, endpoint_id, repository_url, user_name, user_password))
        return self.responses.pop(0)


def test_create_stack_retries_after_cleaning_stale_compose_workspace(monkeypatch, tmp_path):
    workdir = tmp_path / 'compose' / '2'
    workdir.mkdir(parents=True)
    (workdir / 'src').mkdir()
    error_text = '{"details":"open ' + str(workdir / 'src' / 'php.ini') + ': is a directory"}'
    fake_api = FakePortainerApi([
        FakeResponse(400, text=error_text),
        FakeResponse(200, payload={'Id': 2}),
    ])

    manager = object.__new__(PortainerManager)
    manager.portainer = fake_api
    monkeypatch.setattr(manager, '_extract_compose_workdir', lambda message: str(workdir))

    result = manager.create_stack_from_repository('moodle_qy7wv', 1, 'http://repo', 'user', 'pwd')

    assert result == {'Id': 2}
    assert len(fake_api.calls) == 2
    assert not workdir.exists()