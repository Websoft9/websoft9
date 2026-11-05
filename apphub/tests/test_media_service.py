"""The standalone media service: upload endpoint used for application logos and screenshots.

`src/media.py` is mounted as its own Starlette app, so its handlers are called directly here with a
minimal fake request instead of through the main API.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json

from src import media


class FakeUploadFile:
    def __init__(self, filename, content, error=None):
        self.filename = filename
        self._content = content
        self._error = error

    async def read(self):
        if self._error:
            raise self._error
        return self._content


class FakeForm:
    def __init__(self, file):
        self._file = file

    def get(self, key):
        return self._file if key == 'file' else None


class FakeRequest:
    def __init__(self, form=None, form_error=None):
        self._form = form
        self._form_error = form_error

    async def form(self):
        if self._form_error:
            raise self._form_error
        return self._form


def _body(response):
    return json.loads(response.body)


@pytest.fixture(autouse=True)
def media_dir(tmp_path, monkeypatch):
    directory = tmp_path / 'media'
    monkeypatch.setattr(media, 'MEDIA_DIR', str(directory))
    return directory


def test_health_check_answers_ok():
    import asyncio

    response = asyncio.run(media.healthz(None))

    assert response.status_code == 200
    assert _body(response) == {'status': 'ok'}


def test_upload_stores_the_file_and_returns_its_url(media_dir):
    import asyncio

    request = FakeRequest(FakeForm(FakeUploadFile('logo.png', b'\x89PNG data')))

    response = asyncio.run(media.upload(request))

    assert response.status_code == 200
    url = _body(response)['url']
    assert url.startswith('/api/media/images/')
    stored = media_dir / url.rsplit('/', 1)[-1]
    assert stored.read_bytes() == b'\x89PNG data'
    # 文件名被替换成 uuid,避免同名覆盖和路径注入
    assert stored.suffix == '.png'
    assert 'logo' not in stored.name


def test_upload_requires_a_file():
    import asyncio

    response = asyncio.run(media.upload(FakeRequest(FakeForm(None))))

    assert response.status_code == 400
    assert _body(response) == {'error': 'No file provided'}


def test_upload_accepts_a_file_without_an_extension(media_dir):
    import asyncio

    response = asyncio.run(media.upload(FakeRequest(FakeForm(FakeUploadFile('README', b'text')))))

    assert response.status_code == 200
    stored = media_dir / _body(response)['url'].rsplit('/', 1)[-1]
    assert stored.suffix == ''
    assert stored.read_bytes() == b'text'


def test_upload_reports_a_read_failure():
    import asyncio

    request = FakeRequest(FakeForm(FakeUploadFile('logo.png', b'', error=OSError('disk gone'))))

    response = asyncio.run(media.upload(request))

    assert response.status_code == 500
    assert 'disk gone' in _body(response)['error']


def test_upload_reports_a_broken_multipart_body():
    import asyncio

    response = asyncio.run(media.upload(FakeRequest(form_error=ValueError('malformed multipart'))))

    assert response.status_code == 500
    assert 'malformed multipart' in _body(response)['error']


def test_media_directory_is_created_on_demand(media_dir):
    import asyncio

    assert not media_dir.exists()

    asyncio.run(media.upload(FakeRequest(FakeForm(FakeUploadFile('a.txt', b'x')))))

    assert media_dir.is_dir()
    assert os.listdir(media_dir)
