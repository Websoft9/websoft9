import json
import sys
from pathlib import Path

from click.testing import CliRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli import apphub_cli


def test_dispatch_auto_download_calls_the_loopback_apphub_endpoint(tmp_path, monkeypatch):
    secret_file = tmp_path / "trust_key"
    secret_file.write_text("dispatch-secret\n", encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_INTERNAL_GATEWAY_TRUST_KEY_FILE", str(secret_file))
    captured = {}

    class Response:
        def read(self):
            return json.dumps({"started": True}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["secret"] = dict(request.header_items())["X-websoft9-upgrade-dispatch-secret"]
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(apphub_cli, "urlopen", fake_urlopen)

    assert apphub_cli._dispatch_auto_download() is True
    assert captured == {
        "url": apphub_cli.UPGRADE_DISPATCH_URL,
        "secret": "dispatch-secret",
        "timeout": 5,
    }


def test_check_update_dispatches_instead_of_starting_a_cli_thread(monkeypatch):
    class Checker:
        def ensure_latest_version(self, **kwargs):
            assert kwargs == {"channel": "dev", "force": True}
            return "2.4.4"

    monkeypatch.setattr(apphub_cli, "read_release_channel", lambda: "dev")
    monkeypatch.setattr(apphub_cli, "ReleaseVersionChecker", Checker)
    monkeypatch.setattr(apphub_cli, "_dispatch_auto_download", lambda: True)

    result = CliRunner().invoke(apphub_cli.cli, ["check-update"])

    assert result.exit_code == 0
    assert "Latest dev release: 2.4.4" in result.output
    assert "Upgrade download started in the background" in result.output