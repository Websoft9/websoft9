import sys
import types
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

module_path = PROJECT_ROOT / 'src' / 'services' / 'portainer_manager.py'
module_spec = importlib.util.spec_from_file_location('real_portainer_manager', module_path)
portainer_manager_module = importlib.util.module_from_spec(module_spec)
assert module_spec and module_spec.loader
module_spec.loader.exec_module(portainer_manager_module)
PortainerManager = portainer_manager_module.PortainerManager
extract_portainer_error_message = portainer_manager_module._extract_portainer_error_message


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


def test_extract_portainer_error_message_prefers_message_when_details_missing():
    payload = '{"message":"container cannot be started twice"}'

    assert extract_portainer_error_message(payload) == 'container cannot be started twice'


def test_extract_portainer_error_message_keeps_plain_text_when_not_json():
    payload = 'driver failed programming external connectivity'

    assert extract_portainer_error_message(payload) == payload


def _build_manager(fake_api):
    manager = PortainerManager.__new__(PortainerManager)
    manager.portainer = fake_api
    return manager


def test_create_stack_retries_after_cleaning_stale_compose_workspace(monkeypatch, tmp_path):
    workdir = tmp_path / 'compose' / '2'
    workdir.mkdir(parents=True)
    (workdir / 'src').mkdir()
    error_text = '{"details":"open ' + str(workdir / 'src' / 'php.ini') + ': is a directory"}'
    fake_api = FakePortainerApi([
        FakeResponse(400, text=error_text),
        FakeResponse(200, payload={'Id': 2}),
    ])

    manager = _build_manager(fake_api)
    monkeypatch.setattr(manager, '_extract_compose_workdir', lambda message: str(workdir))

    result = manager.create_stack_from_repository('moodle_qy7wv', 1, 'http://repo', 'user', 'pwd')

    assert result == {'Id': 2}
    assert len(fake_api.calls) == 2
    assert not workdir.exists()