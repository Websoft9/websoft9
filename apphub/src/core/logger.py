
from __future__ import annotations

import contextvars
import logging
import logging.config
import os
import sys
from pathlib import Path


_request_id_var = contextvars.ContextVar("apphub_request_id", default="-")
_tracking_id_var = contextvars.ContextVar("apphub_tracking_id", default="-")
_stage_var = contextvars.ContextVar("apphub_stage", default="-")


class ContextDefaultsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", _request_id_var.get())
        record.tracking_id = getattr(record, "tracking_id", _tracking_id_var.get())
        record.stage = getattr(record, "stage", _stage_var.get())
        return True


def set_request_id(request_id: str | None) -> None:
    _request_id_var.set(request_id or "-")


def set_tracking_context(tracking_id: str | None = None, stage: str | None = None) -> None:
    _tracking_id_var.set(tracking_id or "-")
    _stage_var.set(stage or "-")


def clear_logging_context() -> None:
    _request_id_var.set("-")
    _tracking_id_var.set("-")
    _stage_var.set("-")


class Logger:
    def __init__(self) -> None:
        self._configure_logging()
        self._app_logger = logging.getLogger("apphub")
        self._access_logger = logging.getLogger("apphub.access")
        self._error_logger = logging.getLogger("apphub.error")
        self._install_logger = logging.getLogger("apphub.install")

    def _configure_logging(self) -> None:
        log_folder = Path(os.getenv("WEBSOFT9_LOG_DIR") or os.path.join(os.getcwd(), "logs"))
        log_folder.mkdir(parents=True, exist_ok=True)

        formatter = {
            "format": "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s tracking_id=%(tracking_id)s stage=%(stage)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        }

        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "filters": {
                    "context_defaults": {
                        "()": ContextDefaultsFilter,
                    }
                },
                "formatters": {
                    "standard": formatter,
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filters": ["context_defaults"],
                        "stream": "ext://sys.stdout",
                    },
                    "app_file": {
                        "class": "logging.handlers.TimedRotatingFileHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filters": ["context_defaults"],
                        "filename": str(log_folder / "apphub.log"),
                        "when": "midnight",
                        "interval": 1,
                        "backupCount": 30,
                        "encoding": "utf-8",
                    },
                    "access_file": {
                        "class": "logging.handlers.TimedRotatingFileHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filters": ["context_defaults"],
                        "filename": str(log_folder / "apphub_access.log"),
                        "when": "midnight",
                        "interval": 1,
                        "backupCount": 30,
                        "encoding": "utf-8",
                    },
                    "error_file": {
                        "class": "logging.handlers.TimedRotatingFileHandler",
                        "level": "ERROR",
                        "formatter": "standard",
                        "filters": ["context_defaults"],
                        "filename": str(log_folder / "apphub_error.log"),
                        "when": "midnight",
                        "interval": 1,
                        "backupCount": 30,
                        "encoding": "utf-8",
                    },
                    "install_file": {
                        "class": "logging.handlers.TimedRotatingFileHandler",
                        "level": "INFO",
                        "formatter": "standard",
                        "filters": ["context_defaults"],
                        "filename": str(log_folder / "apphub_install.log"),
                        "when": "midnight",
                        "interval": 1,
                        "backupCount": 30,
                        "encoding": "utf-8",
                    },
                },
                "loggers": {
                    "apphub": {
                        "handlers": ["console", "app_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "apphub.access": {
                        "handlers": ["console", "access_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "apphub.error": {
                        "handlers": ["console", "error_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "apphub.install": {
                        "handlers": ["console", "install_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn": {
                        "handlers": ["console", "app_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["console", "access_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "uvicorn.error": {
                        "handlers": ["console", "error_file"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {
                    "handlers": ["console", "app_file"],
                    "level": "INFO",
                },
            }
        )

        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(line_buffering=True)
            except Exception:
                pass

    def access(self, message: str, *args, **kwargs) -> None:
        self._access_logger.info(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        self._app_logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        self._app_logger.warning(message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs) -> None:
        self._app_logger.debug(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self._error_logger.error(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        self._error_logger.exception(message, *args, **kwargs)

    def install(self, message: str, *args, **kwargs) -> None:
        self._install_logger.info(message, *args, **kwargs)


logger = Logger()
