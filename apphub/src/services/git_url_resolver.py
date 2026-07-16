import os
from urllib.parse import urlparse, urlunparse


def normalize_runtime_git_url(remote_url: str) -> str:
    try:
        parsed = urlparse(remote_url)
    except Exception:
        return remote_url

    if not parsed.scheme or not parsed.netloc:
        return remote_url

    runtime_layout = (os.getenv("WEBSOFT9_RUNTIME_LAYOUT") or "").strip().lower()
    public_origin = (os.getenv("WEBSOFT9_PLATFORM_PUBLIC_ORIGIN") or "").strip()
    public_host = urlparse(public_origin).hostname if public_origin else ""

    if runtime_layout != "single-container-target":
        return remote_url

    if parsed.hostname not in {"websoft9-git", "localhost", "127.0.0.1", public_host}:
        return remote_url

    normalized_path = parsed.path
    if normalized_path.startswith("/w9git/"):
        normalized_path = normalized_path[len("/w9git"):]

    return urlunparse(
        parsed._replace(
            scheme="http",
            netloc="127.0.0.1:3001",
            path=normalized_path,
        )
    )