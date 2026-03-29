import json
import logging
from collections.abc import Generator
from pathlib import Path

import pytest

import borgboi.config as config_module
from borgboi.config import Config, LoggingConfig
from borgboi.core.logging import LOG_FILE_NAME, configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset_logging(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None]:
    monkeypatch.setattr(config_module, "resolve_home_dir", lambda: tmp_path)
    yield
    configure_logging(Config(logging=LoggingConfig(enabled=False)))


def _read_log_entries(log_file: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]


def test_configure_logging_disabled_does_not_create_logs_dir() -> None:
    cfg = Config(logging=LoggingConfig(enabled=False))

    assert configure_logging(cfg) is None
    assert not cfg.logs_dir.exists()


def test_configure_logging_writes_stdlib_and_structlog_events() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True))

    log_file = configure_logging(cfg)

    assert log_file == cfg.logs_dir / LOG_FILE_NAME
    assert log_file is not None

    logging.getLogger("borgboi.storage.sqlite").warning("sqlite warning")
    get_logger("borgboi.cli.main").info("structured event", repo="demo")

    entries = _read_log_entries(log_file)

    assert any(entry["event"] == "Application logging configured" for entry in entries)
    assert any(
        entry["event"] == "sqlite warning"
        and entry["logger"] == "borgboi.storage.sqlite"
        and entry["level"] == "warning"
        for entry in entries
    )
    assert any(
        entry["event"] == "structured event" and entry["logger"] == "borgboi.cli.main" and entry["repo"] == "demo"
        for entry in entries
    )


def test_configure_logging_filters_debug_logs_by_default() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=False)

    log_file = configure_logging(cfg)
    assert log_file is not None

    logging.getLogger("borgboi.debug").debug("hidden debug event")

    entries = _read_log_entries(log_file)
    assert all(entry["event"] != "hidden debug event" for entry in entries)


def test_configure_logging_honors_configured_log_level() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True, level="error"))

    log_file = configure_logging(cfg)
    assert log_file is not None

    logging.getLogger("borgboi.levels").warning("hidden warning event")
    logging.getLogger("borgboi.levels").error("visible error event")

    entries = _read_log_entries(log_file)
    assert all(entry["event"] != "hidden warning event" for entry in entries)
    assert any(entry["event"] == "visible error event" and entry["level"] == "error" for entry in entries)


def test_configure_logging_emits_debug_logs_when_debug_enabled() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)

    log_file = configure_logging(cfg)
    assert log_file is not None

    logging.getLogger("borgboi.debug").debug("visible debug event")

    entries = _read_log_entries(log_file)
    assert any(entry["event"] == "visible debug event" and entry["level"] == "debug" for entry in entries)


def test_configure_logging_rotates_log_files() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True, max_bytes=300, backup_count=1))

    log_file = configure_logging(cfg)
    assert log_file is not None

    logger = logging.getLogger("borgboi.rotation")
    for _ in range(8):
        logger.info("x" * 200)

    rotated_file = log_file.with_name(f"{log_file.name}.1")
    assert rotated_file.exists()


def test_configure_logging_replaces_existing_managed_handler() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True))

    log_file = configure_logging(cfg)
    assert log_file is not None

    configure_logging(cfg)
    logging.getLogger("borgboi.test").info("one event")

    entries = _read_log_entries(log_file)
    assert sum(1 for entry in entries if entry["event"] == "one event") == 1
