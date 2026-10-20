from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import re
import sys
from typing import Any, Callable, Iterator

import click
from pydantic import BaseModel

from src.core.exception import CustomException


MAX_TEXT_BUDGET_BYTES = 64 * 1024

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|authorization)",
    re.IGNORECASE,
)
_URI_CREDENTIALS_PATTERN = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:)([^@\s/]+)(@)")
_BEARER_PATTERN = re.compile(r"(\b(?:Authorization|Bearer)\b[\s:=]+(?:Bearer\s+)?)([A-Za-z0-9._~+/=-]{6,})", re.IGNORECASE)
_TEXT_ASSIGNMENT_PATTERN = re.compile(
    rf"(?P<prefix>(?P<quote>[\"']?)(?P<key>[\w.-]*(?:{_SENSITIVE_KEY_PATTERN.pattern})[\w.-]*)(?P=quote)[ \t]*[:=][ \t]*)"
    r"(?P<value>\"(?:\\.|[^\"\\])*(?:\"|\Z)|'(?:''|[^'])*(?:'|\Z)|[^\r\n,;}\]]*)",
    re.IGNORECASE,
)
_YAML_SECRET_LINE_PATTERN = re.compile(
    r"^(?:[-+])?(?P<indent>[ \t]*)(?:-[ \t]*)?[\"']?(?P<key>[A-Za-z_][\w.-]*)[\"']?[ \t]*:[ \t]*"
)
_PEM_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)


def is_sensitive_key(key: str) -> bool:
    normalized = str(key or "").strip()
    return bool(_SENSITIVE_KEY_PATTERN.search(normalized))


def mask_sensitive_text(text: str | None) -> str:
    if not text:
        return ""
    masked = str(text)
    masked = _PEM_PRIVATE_KEY_PATTERN.sub("******", masked)
    masked = _URI_CREDENTIALS_PATTERN.sub(r"\1******\3", masked)
    masked = _BEARER_PATTERN.sub(r"\1******", masked)
    decoder = json.JSONDecoder()
    parts: list[str] = []
    position = 0
    for candidate in re.finditer(r"[\[{]", masked):
        if candidate.start() < position:
            continue
        try:
            value, end = decoder.raw_decode(masked, candidate.start())
        except ValueError:
            continue
        parts.extend((masked[position:candidate.start()], json.dumps(sanitize_value(value), ensure_ascii=False)))
        position = end
    if parts:
        masked = "".join(parts) + masked[position:]
    lines = masked.splitlines(keepends=True)
    bounded_lines: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        block = _YAML_SECRET_LINE_PATTERN.match(line)
        if block and is_sensitive_key(block["key"]):
            bounded_lines.append(line[:block.end()] + "******\n")
            indent = len(block["indent"])
            index += 1
            while index < len(lines):
                following = lines[index]
                content = following.lstrip("+-") if following.startswith(("+", "-")) else following
                if content.strip() and len(content) - len(content.lstrip(" \t")) <= indent:
                    break
                index += 1
            continue
        bounded_lines.append(line)
        index += 1
    masked = "".join(bounded_lines)

    def redact_assignment(match: re.Match[str]) -> str:
        if not is_sensitive_key(match["key"]):
            return match[0]
        quote = match["value"][:1]
        replacement = f"{quote}******{quote}" if quote in {"'", '"'} else "******"
        return match["prefix"] + replacement

    masked = _TEXT_ASSIGNMENT_PATTERN.sub(redact_assignment, masked)
    return masked


def sanitize_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return sanitize_value(value.model_dump())
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if is_sensitive_key(key_str) and not isinstance(item, bool):
                sanitized[key_str] = "******" if item not in (None, "") else item
            else:
                sanitized[key_str] = sanitize_value(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [sanitize_value(item) for item in value]
    if isinstance(value, str):
        return mask_sensitive_text(value)
    return value


def truncate_utf8_text(text: str, max_bytes: int = MAX_TEXT_BUDGET_BYTES, *, keep_tail: bool = True) -> tuple[str, bool]:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False
    if max_bytes <= 0:
        return "", True
    sliced = encoded[-max_bytes:] if keep_tail else encoded[:max_bytes]
    decoded = sliced.decode("utf-8", errors="ignore")
    return decoded, True


class CLIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Any = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = mask_sensitive_text(message)
        self.details = sanitize_value(details) if details is not None else None
        self.exit_code = exit_code


def map_exception(exc: Exception) -> CLIError:
    if isinstance(exc, CLIError):
        return exc
    if isinstance(exc, (click.BadParameter, click.UsageError)):
        return CLIError("INVALID_ARGUMENT", exc.format_message(), exit_code=2)
    if isinstance(exc, CustomException):
        status_code = getattr(exc, "status_code", 500)
        message = str(getattr(exc, "message", "") or "Operation failed")
        details = getattr(exc, "details", None)
        detail_text = str(details or message)
        if status_code == 404:
            return CLIError("NOT_FOUND", detail_text, details={"reason": detail_text}, exit_code=1)
        if status_code in {401, 403}:
            return CLIError("PERMISSION_DENIED", detail_text, details={"reason": detail_text}, exit_code=1)
        if status_code == 400:
            return CLIError("INVALID_REQUEST", detail_text, details={"reason": detail_text}, exit_code=1)
        if status_code in {502, 503, 504}:
            return CLIError("DEPENDENCY_UNAVAILABLE", detail_text, details={"reason": detail_text}, exit_code=1)
        return CLIError("OPERATION_FAILED", detail_text, details={"status_code": status_code}, exit_code=1)
    if isinstance(exc, click.ClickException):
        return CLIError("OPERATION_FAILED", exc.format_message(), exit_code=1)
    if isinstance(exc, TimeoutError):
        return CLIError("DEPENDENCY_UNAVAILABLE", str(exc) or "Operation timed out", exit_code=1)
    if isinstance(exc, (FileNotFoundError, ConnectionError)):
        return CLIError("DEPENDENCY_UNAVAILABLE", str(exc), exit_code=1)
    return CLIError("INTERNAL_ERROR", str(exc) or type(exc).__name__, exit_code=1)


@contextmanager
def route_console_logs_to_stderr() -> Iterator[None]:
    swapped: list[tuple[logging.StreamHandler, Any]] = []
    loggers = [
        logging.getLogger(),
        logging.getLogger("apphub"),
        logging.getLogger("apphub.access"),
        logging.getLogger("apphub.error"),
        logging.getLogger("apphub.install"),
    ]
    seen_handlers: set[int] = set()
    for log in loggers:
        for handler in getattr(log, "handlers", []):
            if id(handler) in seen_handlers:
                continue
            seen_handlers.add(id(handler))
            if isinstance(handler, logging.StreamHandler) and getattr(handler, "stream", None) is sys.stdout:
                swapped.append((handler, handler.stream))
                handler.setStream(sys.stderr)
    try:
        yield
    finally:
        for handler, original_stream in swapped:
            try:
                handler.setStream(original_stream)
            except Exception:
                pass


def build_envelope(
    *,
    ok: bool,
    code: str,
    data: Any = None,
    error: dict[str, Any] | None = None,
    truncated: bool = False,
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "code": str(code),
        "data": sanitize_value(data) if data is not None else None,
        "error": sanitize_value(error) if error is not None else None,
        "meta": {"truncated": bool(truncated)},
    }


def emit_success(
    data: Any,
    *,
    as_json: bool,
    text_renderer: Callable[[Any], str] | None = None,
    truncated: bool = False,
) -> None:
    sanitized = sanitize_value(data)
    if as_json:
        envelope = build_envelope(ok=True, code="OK", data=sanitized, error=None, truncated=truncated)
        click.echo(json.dumps(envelope, ensure_ascii=False))
        return

    if text_renderer is not None:
        rendered = text_renderer(sanitized)
    elif isinstance(sanitized, str):
        rendered = sanitized
    else:
        rendered = json.dumps(sanitized, ensure_ascii=False, indent=2)
    if rendered:
        click.echo(mask_sensitive_text(rendered))


def emit_error(error: CLIError, *, as_json: bool, truncated: bool = False) -> None:
    if as_json:
        payload = build_envelope(
            ok=False,
            code=error.code,
            data=None,
            error={"message": error.message, "details": error.details},
            truncated=truncated,
        )
        click.echo(json.dumps(payload, ensure_ascii=False))
    else:
        click.echo(f"Error [{error.code}]: {error.message}", err=True)
    raise click.exceptions.Exit(error.exit_code)


def run_cli_action(
    action: Callable[[], Any],
    *,
    as_json: bool,
    text_renderer: Callable[[Any], str] | None = None,
) -> Any:
    with route_console_logs_to_stderr():
        try:
            result = action()
            truncated = False
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], bool):
                data, truncated = result
            else:
                data = result
        except click.exceptions.Exit:
            raise
        except Exception as exc:
            cli_error = map_exception(exc)
            emit_error(cli_error, as_json=as_json)
            return None

    emit_success(data, as_json=as_json, text_renderer=text_renderer, truncated=truncated)
    return data


def _args_request_json(args: list[str] | tuple[str, ...]) -> bool:
    for token in args:
        if token == "--":
            break
        if token == "--json":
            return True
    return False


class JsonAwareCommand(click.Command):
    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: Any,
    ) -> click.Context:
        raw_args = list(args)
        try:
            return super().make_context(info_name, args, parent=parent, **extra)
        except click.ClickException as exc:
            if _args_request_json(raw_args):
                cli_error = map_exception(exc)
                emit_error(cli_error, as_json=True)
            raise


class JsonAwareGroup(click.Group):
    command_class = JsonAwareCommand

    def group(self, *args: Any, **kwargs: Any):
        kwargs.setdefault("cls", JsonAwareGroup)
        return super().group(*args, **kwargs)


def upgrade_group_commands_to_json_aware(
    group: click.Group,
    *,
    exclude_commands: set[str] | None = None,
) -> None:
    excluded = exclude_commands or set()
    for name, cmd in list(group.commands.items()):
        if name in excluded:
            continue
        if isinstance(cmd, click.Group):
            upgrade_group_commands_to_json_aware(cmd)
        elif isinstance(cmd, click.Command) and not isinstance(cmd, JsonAwareCommand):
            cmd.__class__ = JsonAwareCommand
