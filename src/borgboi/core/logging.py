"""Application logging configuration for borgboi."""

from __future__ import annotations

import logging as stdlib_logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, cast

import structlog

from borgboi.config import Config

LOG_FILE_NAME = "borgboi.log"
_HANDLER_NAME = "borgboi-local-file"
_LOGGER_NAMESPACE = "borgboi"
_LOG_LEVELS = {
    "debug": stdlib_logging.DEBUG,
    "info": stdlib_logging.INFO,
    "warning": stdlib_logging.WARNING,
    "error": stdlib_logging.ERROR,
    "critical": stdlib_logging.CRITICAL,
}


def _build_shared_processors() -> list[Any]:
    return [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _configure_structlog() -> None:
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            *_build_shared_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _build_file_handler(log_file: Path, level: int, max_bytes: int, backup_count: int) -> stdlib_logging.Handler:
    handler = RotatingFileHandler(
        log_file,
        encoding="utf-8",
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    handler.set_name(_HANDLER_NAME)
    handler.setLevel(level)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=_build_shared_processors(),
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(sort_keys=True),
            ],
        )
    )
    return handler


def _remove_managed_handlers(logger: stdlib_logging.Logger) -> None:
    for handler in list(logger.handlers):
        if handler.get_name() != _HANDLER_NAME:
            continue
        logger.removeHandler(handler)
        handler.close()


def _get_log_level(config: Config) -> int:
    if config.debug:
        return stdlib_logging.DEBUG
    return _LOG_LEVELS[config.logging.level]


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger for borgboi application code."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name or _LOGGER_NAMESPACE))


def configure_logging(config: Config) -> Path | None:
    """Configure file-backed application logging when enabled in config."""
    namespace_logger = stdlib_logging.getLogger(_LOGGER_NAMESPACE)
    _remove_managed_handlers(namespace_logger)
    _configure_structlog()

    if not config.logging.enabled:
        namespace_logger.setLevel(stdlib_logging.NOTSET)
        namespace_logger.propagate = True
        return None

    level = _get_log_level(config)
    log_file = config.logs_dir / LOG_FILE_NAME
    log_file.parent.mkdir(parents=True, exist_ok=True)

    namespace_logger.setLevel(level)
    namespace_logger.addHandler(
        _build_file_handler(
            log_file,
            level,
            config.logging.max_bytes,
            config.logging.backup_count,
        )
    )
    namespace_logger.propagate = False

    get_logger(__name__).info(
        "Application logging configured",
        log_file=str(log_file),
        log_level=stdlib_logging.getLevelName(level).lower(),
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
    )
    return log_file
