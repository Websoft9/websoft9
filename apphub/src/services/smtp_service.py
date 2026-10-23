"""Platform SMTP settings and email sending service."""

from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import threading
from dataclasses import dataclass
from email.header import Header
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Any, Optional

from src.core.exception import CustomException
from src.core.logger import logger

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_ENCRYPTIONS = {"starttls", "ssl", "none"}
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_ENCRYPTION = "starttls"
DEFAULT_SENDER_NAME = "Websoft9"
SMTP_TIMEOUT_SECONDS = 15


def _validate_email_address(value: str, field_label: str = "Email") -> str:
    normalized = str(value or "").strip()
    if not normalized or not EMAIL_PATTERN.match(normalized) or any(ch in normalized for ch in "\r\n"):
        raise CustomException(400, "Invalid Request", f"{field_label} must be a valid email address")
    return normalized


def _validate_no_header_injection(value: str, field_label: str) -> str:
    normalized = str(value or "").strip()
    if any(ch in normalized for ch in "\r\n\x00"):
        raise CustomException(400, "Invalid Request", f"{field_label} contains invalid characters")
    return normalized


@dataclass(frozen=True)
class SmtpSettings:
    enabled: bool = False
    host: str = ""
    port: int = DEFAULT_SMTP_PORT
    encryption: str = DEFAULT_SMTP_ENCRYPTION
    username: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = DEFAULT_SENDER_NAME

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.host.strip() and self.from_email.strip() and 1 <= int(self.port) <= 65535)

    def masked(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "host": self.host,
            "port": int(self.port),
            "encryption": self.encryption,
            "username": self.username,
            "password_set": bool(self.password),
            "from_email": self.from_email,
            "from_name": self.from_name,
        }


class SmtpService:
    _lock = threading.RLock()

    def __init__(self, data_dir: Optional[str] = None):
        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        self.data_dir = Path(data_dir or os.getenv("WEBSOFT9_SMTP_DATA_DIR") or f"{data_root}/config/smtp")
        self.config_file = self.data_dir / "smtp.json"

    def get_settings(self) -> SmtpSettings:
        with self._lock:
            if not self.config_file.is_file():
                return SmtpSettings()
            try:
                raw = json.loads(self.config_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error(f"Failed to read SMTP settings: {exc}")
                return SmtpSettings()

        try:
            port = int(raw.get("port", DEFAULT_SMTP_PORT))
        except (TypeError, ValueError):
            port = DEFAULT_SMTP_PORT
        encryption = str(raw.get("encryption") or DEFAULT_SMTP_ENCRYPTION).strip().lower()
        if encryption not in VALID_ENCRYPTIONS:
            encryption = DEFAULT_SMTP_ENCRYPTION

        return SmtpSettings(
            enabled=bool(raw.get("enabled", False)),
            host=str(raw.get("host") or "").strip(),
            port=port if 1 <= port <= 65535 else DEFAULT_SMTP_PORT,
            encryption=encryption,
            username=str(raw.get("username") or "").strip(),
            password=str(raw.get("password") or ""),
            from_email=str(raw.get("from_email") or "").strip(),
            from_name=str(raw.get("from_name") or "").strip(),
        )

    def get_masked_settings(self) -> dict[str, Any]:
        return self.get_settings().masked()

    def is_ready(self) -> bool:
        return self.get_settings().is_configured

    def resolve_effective_settings(
        self,
        *,
        enabled: bool,
        host: str,
        port: int,
        encryption: str,
        username: str = "",
        password: Optional[str] = None,
        from_email: str = "",
        from_name: str = DEFAULT_SENDER_NAME,
        require_complete: bool = False,
    ) -> SmtpSettings:
        current = self.get_settings()
        normalized_host = _validate_no_header_injection(host, "SMTP host")
        if normalized_host and ("://" in normalized_host or "/" in normalized_host or any(ch.isspace() for ch in normalized_host)):
            raise CustomException(400, "Invalid Request", "SMTP host must be a valid hostname or IP address without scheme or path")
        normalized_encryption = str(encryption or DEFAULT_SMTP_ENCRYPTION).strip().lower()
        if normalized_encryption not in VALID_ENCRYPTIONS:
            raise CustomException(400, "Invalid Request", "Encryption must be one of: starttls, ssl, none")

        try:
            normalized_port = int(port)
        except (TypeError, ValueError):
            raise CustomException(400, "Invalid Request", "SMTP port must be an integer between 1 and 65535")
        if normalized_port < 1 or normalized_port > 65535:
            raise CustomException(400, "Invalid Request", "SMTP port must be an integer between 1 and 65535")

        normalized_username = _validate_no_header_injection(username, "SMTP username")
        resolved_password = current.password if password is None else str(password)
        normalized_from_email = str(from_email or "").strip()
        if normalized_from_email:
            normalized_from_email = _validate_email_address(normalized_from_email, "Sender email")
        normalized_from_name = _validate_no_header_injection(from_name or "", "Sender name")

        should_require_fields = bool(
            enabled
            or require_complete
            or normalized_host
            or normalized_from_email
            or normalized_username
            or (password is not None and bool(str(password).strip()))
            or current.host
            or current.from_email
        )
        if should_require_fields:
            if not normalized_host:
                raise CustomException(400, "Invalid Request", "SMTP host is required")
            if not normalized_from_email:
                raise CustomException(400, "Invalid Request", "Sender email is required")
            if normalized_username and not resolved_password:
                raise CustomException(400, "Invalid Request", "SMTP password is required when username is set")

        return SmtpSettings(
            enabled=bool(enabled),
            host=normalized_host,
            port=normalized_port,
            encryption=normalized_encryption,
            username=normalized_username,
            password=resolved_password,
            from_email=normalized_from_email,
            from_name=normalized_from_name,
        )

    def save_settings(
        self,
        *,
        enabled: bool,
        host: str,
        port: int,
        encryption: str,
        username: str = "",
        password: Optional[str] = None,
        from_email: str = "",
        from_name: str = DEFAULT_SENDER_NAME,
    ) -> dict[str, Any]:
        settings = self.resolve_effective_settings(
            enabled=enabled,
            host=host,
            port=port,
            encryption=encryption,
            username=username,
            password=password,
            from_email=from_email,
            from_name=from_name,
            require_complete=False,
        )
        payload = {
            "enabled": settings.enabled,
            "host": settings.host,
            "port": settings.port,
            "encryption": settings.encryption,
            "username": settings.username,
            "password": settings.password,
            "from_email": settings.from_email,
            "from_name": settings.from_name,
        }
        with self._lock:
            self.data_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
            try:
                os.chmod(self.data_dir, 0o700)
            except OSError:
                pass
            temp_file = self.data_dir / "smtp.json.tmp"
            descriptor = os.open(temp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_file, self.config_file)
            try:
                os.chmod(self.config_file, 0o600)
            except OSError:
                pass
        return settings.masked()

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        settings: Optional[SmtpSettings] = None,
    ) -> None:
        effective = settings or self.get_settings()
        if not effective.host or not effective.from_email:
            raise CustomException(400, "SMTP Not Configured", "SMTP server is not configured")
        recipient = _validate_email_address(to_email, "Recipient email")
        clean_subject = _validate_no_header_injection(subject, "Email subject")

        message = EmailMessage()
        message["Subject"] = str(Header(clean_subject, "utf-8"))
        message["From"] = formataddr((str(Header(effective.from_name or DEFAULT_SENDER_NAME, "utf-8")), effective.from_email))
        message["To"] = recipient
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid()
        message.set_content(body_text, charset="utf-8")

        try:
            self._deliver_message(effective, message)
        except CustomException:
            raise
        except smtplib.SMTPAuthenticationError as exc:
            logger.warning(f"SMTP authentication failed for host {effective.host}:{effective.port}")
            raise CustomException(
                400,
                "SMTP Authentication Failed",
                "SMTP authentication failed. Please check the username and password",
            ) from exc
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            logger.warning(f"SMTP delivery failed for host {effective.host}:{effective.port}: {type(exc).__name__}")
            raise CustomException(
                502,
                "SMTP Delivery Failed",
                f"Unable to send email via SMTP server ({type(exc).__name__})",
            ) from exc

    def _deliver_message(self, settings: SmtpSettings, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        if settings.encryption == "ssl":
            with smtplib.SMTP_SSL(settings.host, settings.port, timeout=SMTP_TIMEOUT_SECONDS, context=context) as client:
                client.ehlo()
                if settings.username:
                    client.login(settings.username, settings.password)
                client.send_message(message)
            return

        with smtplib.SMTP(settings.host, settings.port, timeout=SMTP_TIMEOUT_SECONDS) as client:
            client.ehlo()
            if settings.encryption == "starttls":
                client.starttls(context=context)
                client.ehlo()
            if settings.username:
                client.login(settings.username, settings.password)
            client.send_message(message)

    def send_test_email(
        self,
        *,
        to_email: str,
        enabled: bool = True,
        host: str,
        port: int,
        encryption: str,
        username: str = "",
        password: Optional[str] = None,
        from_email: str = "",
        from_name: str = DEFAULT_SENDER_NAME,
        locale: str = "en",
    ) -> dict[str, Any]:
        recipient = _validate_email_address(to_email, "Test recipient email")
        effective = self.resolve_effective_settings(
            enabled=enabled,
            host=host,
            port=port,
            encryption=encryption,
            username=username,
            password=password,
            from_email=from_email,
            from_name=from_name,
            require_complete=True,
        )
        sender_title = effective.from_name or DEFAULT_SENDER_NAME
        is_zh = str(locale or "en").strip().lower().startswith("zh")
        subject = (
            f"[{sender_title}] 邮件服务配置测试"
            if is_zh
            else f"[{sender_title}] Email Service Configuration Test"
        )
        body_text = (
            f"这是一封来自 {sender_title} 的测试邮件。\n\n"
            "您的 SMTP 邮件服务配置正常，可用于发送系统通知与安全验证邮件。\n"
            if is_zh
            else (
                f"This is a test email from {sender_title}.\n\n"
                "Your SMTP email service is working properly and is ready to send system notifications and security verification emails.\n"
            )
        )
        self.send_email(
            to_email=recipient,
            subject=subject,
            body_text=body_text,
            settings=effective,
        )
        return {"sent": True, "to_email": recipient}
