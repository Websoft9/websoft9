"""The redeploy log stream: what an operator sees while a redeploy runs.

`GET /apps/{app_id}/redeploy` streams newline-delimited JSON. The endpoint wraps the manager call in
a background task and serialises everything through a queue, so the shapes asserted here are the
contract the console renders: one entry per log line, one `error` entry carrying code/message/details,
a terminating `end` entry and a final status line.
"""

import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from support_module_stubs import restore_module_stubs, stub_module

sys.modules.setdefault('aiodocker', types.ModuleType('aiodocker'))
os.environ.setdefault('WEBSOFT9_INSTALL_TRACKING_DIR', tempfile.mkdtemp(prefix='redeploy-stream-tests-'))

git_module = types.ModuleType('git')
git_module.Repo = object
git_module.GitCommandError = RuntimeError
stub_module('git', git_module)
stub_module('jwt', types.ModuleType('jwt'))
keyring_module = types.ModuleType('keyring')
keyring_module.get_password = lambda *args, **kwargs: None
keyring_module.set_password = lambda *args, **kwargs: None
stub_module('keyring', keyring_module)

from src.api.v1.routers import app as app_router
from src.core.exception import CustomException

restore_module_stubs()


class FakeAppManager:
    """Stands in for `AppManger`: either narrates a redeploy or fails."""

    def __init__(self, behaviour):
        self.behaviour = behaviour

    async def redeploy_app(self, app_id, pull_image, endpoint_id, queue=None):
        if queue is None:
            return
        if self.behaviour == 'success':
            await queue.put('Initializing Redeployment')
            await queue.put('Redeployment complete')
            return
        if self.behaviour == 'custom-error':
            raise CustomException(400, 'Invalid Request', 'wordpress_abc Not Found')
        raise RuntimeError('daemon exploded')


async def _drain(response):
    """Reads the streamed body and parses each newline-delimited JSON entry."""
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return [json.loads(chunk) for chunk in chunks]


def _run(monkeypatch, behaviour):
    monkeypatch.setattr(app_router, 'AppManger', lambda: FakeAppManager(behaviour))
    response = asyncio.run(app_router.app_redeploy('wordpress_abc', 21, False))
    return response


def test_redeploy_stream_reports_each_log_line_and_a_success_status(monkeypatch):
    response = _run(monkeypatch, 'success')

    assert response.media_type == 'text/plain'
    entries = asyncio.run(_drain(response))

    logs = [entry['data'] for entry in entries if entry.get('type') == 'log']
    assert logs == ['Initializing Redeployment', 'Redeployment complete']
    assert entries[-1]['status'] == 'success'
    # 每条日志都带时间戳,控制台按它排序
    assert all('timestamp' in entry for entry in entries)


def test_redeploy_stream_forwards_a_known_error_with_its_details(monkeypatch):
    response = _run(monkeypatch, 'custom-error')

    entries = asyncio.run(_drain(response))

    errors = [entry for entry in entries if entry.get('type') == 'error']
    assert len(errors) == 1
    assert errors[0]['code'] == 400
    assert errors[0]['message'] == 'Invalid Request'
    assert errors[0]['details'] == 'wordpress_abc Not Found'
    assert entries[-1]['status'] == 'failed'


def test_redeploy_stream_wraps_an_unexpected_error_as_a_500(monkeypatch):
    response = _run(monkeypatch, 'unexpected-error')

    entries = asyncio.run(_drain(response))

    errors = [entry for entry in entries if entry.get('type') == 'error']
    assert errors[0]['code'] == 500
    assert errors[0]['message'] == 'Internal Server Error'
    assert errors[0]['details'] == 'RuntimeError: daemon exploded'
    assert entries[-1]['status'] == 'failed'


def test_redeploy_stream_closes_after_the_end_marker(monkeypatch):
    response = _run(monkeypatch, 'success')

    entries = asyncio.run(_drain(response))

    # `end` 之后必须立刻收流,否则控制台会一直显示"正在部署"
    end_index = next(index for index, entry in enumerate(entries) if entry.get('type') == 'end')
    assert end_index == len(entries) - 2
    assert set(entries[-1]) == {'status', 'timestamp'}
    assert entries[-1]['status'] == 'success'
