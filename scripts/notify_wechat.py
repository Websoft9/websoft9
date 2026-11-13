#!/usr/bin/env python3
"""Send a release announcement to the WeChat Work (企业微信) robot.

The WeChat API rejects a `markdown.content` longer than 4096 bytes with
`errcode 40058`, and the previous inline `curl` still exited 0, so releases
silently skipped the notification. This helper truncates the notes to fit the
API limit and fails the step when WeChat refuses the message.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

WEBHOOK_TEMPLATE = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
# WeChat caps markdown.content at 4096 bytes; keep room for the notice below.
MAX_CONTENT_BYTES = 3800
TRUNCATION_NOTICE = "\n> …更新内容超过企业微信长度限制已截断，完整清单见 Release 页面。"


def resolve_version(explicit: str, root: Path) -> str:
    if explicit.strip():
        return explicit.strip()
    return str(json.loads((root / "version.json").read_text(encoding="utf-8")).get("version") or "").strip()


def changelog_section(version: str, root: Path) -> str:
    """Return the CHANGELOG section of ``version`` including its heading."""
    pattern = re.compile(rf"^##\s+\[{re.escape(version)}\](?:\s+-\s+.+)?$")
    captured: list[str] = []
    capture = False
    for line in (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if capture:
                break
            capture = bool(pattern.match(line))
        if capture:
            captured.append(line)
    return "\n".join(captured)


def truncate(markdown: str, limit: int = MAX_CONTENT_BYTES) -> str:
    encoded = markdown.encode("utf-8")
    if len(encoded) <= limit:
        return markdown
    notice = TRUNCATION_NOTICE.encode("utf-8")
    head = encoded[: max(0, limit - len(notice))].decode("utf-8", "ignore").rstrip()
    return f"{head}{TRUNCATION_NOTICE}"


def build_markdown(version: str, channel: str, notes: str) -> str:
    return (
        "【Release 通知】\n"
        '> 项目名称：<font color="info">websoft9</font>\n'
        f'> 发布通道：<font color="comment">{channel}</font>\n'
        f'> 最新版本：<font color="comment">{version}</font>\n'
        f"> 更新内容：\n{notes}\n>"
    )


def send(key: str, markdown: str) -> dict[str, Any]:
    payload = json.dumps({"msgtype": "markdown", "markdown": {"content": markdown}}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        WEBHOOK_TEMPLATE.format(key=key),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8", "replace") or "{}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Announce a release in WeChat Work")
    parser.add_argument("--version", default="", help="Version to announce; defaults to version.json")
    parser.add_argument("--channel", default=os.getenv("WX_CHANNEL", "release"), help="Channel label shown in the message")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Repository root")
    parser.add_argument("--dry-run", action="store_true", help="Print the markdown instead of sending it")
    args = parser.parse_args()

    root = Path(args.root)
    version = resolve_version(args.version, root)
    if not version:
        print("::error::No version to announce", file=sys.stderr)
        return 1
    notes = changelog_section(version, root)
    if not notes:
        print(f"::error::CHANGELOG.md is missing a release section for version {version}", file=sys.stderr)
        return 1

    markdown = truncate(build_markdown(version, args.channel, notes))
    print(f"version={version} channel={args.channel} content_bytes={len(markdown.encode('utf-8'))}")
    if args.dry_run:
        print(markdown)
        return 0

    key = os.getenv("WX_WEBHOOK_KEY", "").strip()
    if not key:
        print("::error::WX_WEBHOOK_KEY is not configured", file=sys.stderr)
        return 1

    response = send(key, markdown)
    print(json.dumps(response, ensure_ascii=False))
    if response.get("errcode") != 0:
        print(f"::error::WeChat rejected the notification: {json.dumps(response, ensure_ascii=False)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
