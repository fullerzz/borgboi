"""Application logging configuration for borgboi."""

from __future__ import annotations

import logging as stdlib_logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, cast

import structlog

from borgboi.config import Config
from borgboi.core.telemetry import get_current_span_context

LOG_FILE_BASENAME = "borgboi"
_LOG_FILE_GLOB = f"{LOG_FILE_BASENAME}_*.log"
_HANDLER_NAME = "borgboi-local-file"
_LOGGER_NAMESPACE = "borgboi"
_LOG_LEVELS = {
    "debug": stdlib_logging.DEBUG,
    "info": stdlib_logging.INFO,
    "warning": stdlib_logging.WARNING,
    "error": stdlib_logging.ERROR,
    "critical": stdlib_logging.CRITICAL,
}


class _LoggingState:
    active_log_file: Path | None = None


def _build_shared_processors() -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        _add_otel_trace_context,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _add_otel_trace_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    span_context = get_current_span_context()
    if span_context is None:
        return event_dict

    event_dict["trace_id"] = f"{span_context.trace_id:032x}"
    event_dict["span_id"] = f"{span_context.span_id:016x}"
    event_dict["trace_flags"] = f"{int(span_context.trace_flags):02x}"
    return event_dict


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


def _build_log_file_name(timestamp: datetime | None = None) -> str:
    occurred_at = timestamp or datetime.now().astimezone()
    formatted_timestamp = occurred_at.strftime("%Y-%m-%dT%H_%M_%S")
    return f"{LOG_FILE_BASENAME}_{formatted_timestamp}.log"


def _get_log_file(config: Config) -> Path:
    if _LoggingState.active_log_file is not None and _LoggingState.active_log_file.parent == config.logs_dir:
        return _LoggingState.active_log_file

    _LoggingState.active_log_file = config.logs_dir / _build_log_file_name()
    return _LoggingState.active_log_file


def _prune_session_log_files(logs_dir: Path, active_log_file: Path, backup_count: int) -> None:
    retained_session_count = backup_count + 1
    session_log_files = sorted(logs_dir.glob(_LOG_FILE_GLOB))

    if active_log_file not in session_log_files:
        session_log_files.append(active_log_file)
        session_log_files.sort()

    if len(session_log_files) <= retained_session_count:
        return

    for expired_log_file in session_log_files[:-retained_session_count]:
        expired_log_file.unlink(missing_ok=True)
        for rotated_file in logs_dir.glob(f"{expired_log_file.name}.*"):
            rotated_file.unlink(missing_ok=True)


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

    if not config.logging.enabled:
        _LoggingState.active_log_file = None
        namespace_logger.setLevel(stdlib_logging.NOTSET)
        namespace_logger.propagate = True
        return None

    _configure_structlog()
    level = _get_log_level(config)
    log_file = _get_log_file(config)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    _prune_session_log_files(config.logs_dir, log_file, config.logging.backup_count)

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
