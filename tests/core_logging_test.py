import json
import logging
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest

import borgboi.config as config_module
from borgboi.clients.borg_client import BorgClient
from borgboi.clients.utils.borg_logs import LogMessage
from borgboi.config import Config, LoggingConfig
from borgboi.core.errors import RepositoryNotFoundError, ValidationError
from borgboi.core.logging import configure_logging, get_logger
from borgboi.core.models import BackupOptions
from borgboi.core.orchestrator import Orchestrator
from borgboi.core.output import CollectingOutputHandler, render_command_with_fallback
from borgboi.core.validator import Validator
from borgboi.models import BorgBoiRepo
from borgboi.storage.db import init_db
from borgboi.storage.sqlite import SQLiteStorage


@pytest.fixture(autouse=True)
def _reset_logging(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None]:
    monkeypatch.setattr(config_module, "resolve_home_dir", lambda: tmp_path)
    yield
    configure_logging(Config(logging=LoggingConfig(enabled=False)))


def _read_log_entries(log_file: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]


def _assert_timestamped_log_filename(log_file: Path) -> None:
    assert re.fullmatch(r"borgboi_\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}\.log", log_file.name)


def test_configure_logging_disabled_does_not_create_logs_dir() -> None:
    cfg = Config(logging=LoggingConfig(enabled=False))

    assert configure_logging(cfg) is None
    assert not cfg.logs_dir.exists()


def test_configure_logging_writes_stdlib_and_structlog_events() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True))

    log_file = configure_logging(cfg)

    assert log_file is not None
    assert log_file.parent == cfg.logs_dir
    _assert_timestamped_log_filename(log_file)

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


def test_configure_logging_prunes_old_session_log_files() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True, backup_count=1))
    cfg.logs_dir.mkdir(parents=True)
    expired_log_file = cfg.logs_dir / "borgboi_2026-03-28T19_13_25.log"
    retained_log_file = cfg.logs_dir / "borgboi_2026-03-28T19_13_26.log"
    expired_log_file.write_text("expired\n")
    retained_log_file.write_text("retained\n")
    expired_log_file.with_name(f"{expired_log_file.name}.1").write_text("expired rollover\n")

    log_file = configure_logging(cfg)
    assert log_file is not None

    assert not expired_log_file.exists()
    assert not expired_log_file.with_name(f"{expired_log_file.name}.1").exists()
    assert retained_log_file.exists()
    assert log_file.exists()


def test_configure_logging_replaces_existing_managed_handler() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True))

    log_file = configure_logging(cfg)
    assert log_file is not None

    second_log_file = configure_logging(cfg)
    assert second_log_file == log_file

    logging.getLogger("borgboi.test").info("one event")

    entries = _read_log_entries(log_file)
    assert sum(1 for entry in entries if entry["event"] == "one event") == 1


def test_orchestrator_logs_structured_events_for_create_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True, offline=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    repo_path = tmp_path / "repo"
    passphrase_file = tmp_path / "repo-one.key"
    generated_passphrase = "generated-passphrase"  # noqa: S105
    storage = Mock()
    borg_client = Mock()
    borg_client.info.return_value = None

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    monkeypatch.setattr("borgboi.core.orchestrator.generate_secure_passphrase", lambda: generated_passphrase)
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", lambda name, passphrase: passphrase_file)

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=CollectingOutputHandler(),
    )

    orchestrator.create_repo(repo_path.as_posix(), "/backup/source", "repo-one")

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Creating new Borg repository"
        and entry["logger"] == "borgboi.core.orchestrator"
        and entry["repo_name"] == "repo-one"
        and entry["backup_target"] == "/backup/source"
        for entry in entries
    )
    assert any(
        entry["event"] == "Repository created successfully"
        and entry["logger"] == "borgboi.core.orchestrator"
        and entry["repo_name"] == "repo-one"
        and entry["repo_path"] == repo_path.as_posix()
        for entry in entries
    )
    assert all(entry.get("passphrase") != generated_passphrase for entry in entries)
    assert all(generated_passphrase not in json.dumps(entry) for entry in entries)


def test_orchestrator_logs_import_repo_failure_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True, offline=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    borg_client = Mock()
    borg_client.info.side_effect = RuntimeError("wrong passphrase")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "provided-passphrase")

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=CollectingOutputHandler(),
    )

    with pytest.raises(ValidationError, match="Unable to access Borg repository"):
        orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Failed to access Borg repository"
        and entry["logger"] == "borgboi.core.orchestrator"
        and entry["level"] == "error"
        and entry["repo_path"] == repo_path.resolve().as_posix()
        and "wrong passphrase" in str(entry.get("error", ""))
        for entry in entries
    )


def test_validator_logs_validation_failures_and_config_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    monkeypatch.setattr("borgboi.core.validator.which", lambda _: None)

    with pytest.raises(ValidationError, match="Repository name cannot be empty"):
        Validator.validate_repo_name("")

    config = Config(offline=False)
    config.borg.executable_path = "missing-borg"
    config.borg.compression = "brotli"
    config.borg.retention.keep_daily = 0
    config.borg.retention.keep_weekly = 0
    config.borg.retention.keep_monthly = 0
    config.aws.s3_bucket = ""
    config.aws.dynamodb_repos_table = ""
    config.borg.storage_quota = "fifty"

    warnings = Validator.validate_config(config)
    assert warnings

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Validation failed"
        and entry["logger"] == "borgboi.core.validator"
        and entry["field"] == "name"
        and entry["reason"] == "Repository name cannot be empty"
        for entry in entries
    )
    assert any(
        entry["event"] == "Configuration validation warning"
        and entry["logger"] == "borgboi.core.validator"
        and entry["category"] == "compression"
        and "Invalid compression setting" in str(entry["warning"])
        for entry in entries
    )
    assert any(
        entry["event"] == "Configuration validation completed"
        and entry["logger"] == "borgboi.core.validator"
        and entry["warning_count"] == len(warnings)
        for entry in entries
    )


def test_output_module_logs_render_command_fallback_path() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    output_handler = CollectingOutputHandler()
    render_command_with_fallback(output_handler, "Streaming status", "Streaming done", ["line one\n"])

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Rendering command with output handler render_command"
        and entry["logger"] == "borgboi.core.output"
        and entry["output_handler"] == "CollectingOutputHandler"
        and entry["status"] == "Streaming status"
        for entry in entries
    )


def test_borg_client_logs_structured_create_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    client = BorgClient(config=cfg.borg)
    captured: list[tuple[list[str], str | None]] = []

    def fake_run_streaming_command(cmd: list[str], passphrase: str | None = None) -> Generator[str]:
        captured.append((cmd, passphrase))
        if False:
            yield ""

    monkeypatch.setattr(client, "_run_streaming_command", fake_run_streaming_command)
    excludes_file = tmp_path / "excludes.txt"

    list(
        client.create(
            "/repo",
            "/backup/source",
            archive_name="archive-1",
            options=BackupOptions(compression="lz4"),
            exclude_file=excludes_file.as_posix(),
            passphrase="super-secret",  # noqa: S106
        )
    )

    assert captured

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Creating archive via client"
        and entry["logger"] == "borgboi.clients.borg_client"
        and entry["repo_path"] == "/repo"
        and entry["archive_name"] == "archive-1"
        and entry["backup_target"] == "/backup/source"
        for entry in entries
    )
    assert any(
        entry["event"] == "Archive creation completed via client"
        and entry["logger"] == "borgboi.clients.borg_client"
        and entry["archive_name"] == "archive-1"
        for entry in entries
    )
    assert all(entry.get("passphrase") != "super-secret" for entry in entries)
    assert all("super-secret" not in json.dumps(entry) for entry in entries)


def test_sqlite_storage_logs_structured_save_events(tmp_path: Path) -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    engine = init_db(tmp_path / "storage.db")
    storage = SQLiteStorage(engine=engine)
    repo = BorgBoiRepo(
        path="/repos/test",
        backup_target="/backup/source",
        name="repo-one",
        hostname="host-one",
        os_platform="Darwin",
        metadata=None,
    )

    try:
        storage.save(repo)
    finally:
        storage.close()

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Saving repository to SQLite"
        and entry["logger"] == "borgboi.storage.sqlite"
        and entry["repo_name"] == "repo-one"
        and entry["repo_path"] == "/repos/test"
        for entry in entries
    )
    assert any(
        entry["event"] == "Repository saved to SQLite"
        and entry["logger"] == "borgboi.storage.sqlite"
        and entry["repo_name"] == "repo-one"
        for entry in entries
    )


def test_offline_storage_and_trash_log_structured_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    from borgboi.clients import offline_storage
    from borgboi.clients.utils import trash

    metadata_dir = tmp_path / ".borgboi_metadata"
    trash_dir = tmp_path / ".Trash"
    repo = BorgBoiRepo(
        path="/repos/test",
        backup_target="/backup/source",
        name="repo-one",
        hostname="host-one",
        os_platform="Darwin",
        metadata=None,
    )

    monkeypatch.setattr(offline_storage, "METADATA_DIR", metadata_dir)
    monkeypatch.setattr(trash, "TRASH_PATH", trash_dir)
    trash.get_trash.cache_clear()

    try:
        offline_storage.store_borgboi_repo_metadata(repo)
        assert offline_storage.get_repo(repo.name).path == repo.path
        offline_storage.delete_repo_metadata(repo.name)
    finally:
        trash.get_trash.cache_clear()

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Storing offline repository metadata"
        and entry["logger"] == "borgboi.clients.offline_storage"
        and entry["repo_name"] == "repo-one"
        for entry in entries
    )
    assert any(
        entry["event"] == "Retrieved repository from offline storage"
        and entry["logger"] == "borgboi.clients.offline_storage"
        and entry["repo_path"] == "/repos/test"
        for entry in entries
    )
    assert any(
        entry["event"] == "Moving file to trash"
        and entry["logger"] == "borgboi.clients.utils.trash"
        and entry["file_path"] == str(metadata_dir / "repo-one.json")
        for entry in entries
    )
    assert any(
        entry["event"] == "Deleted offline repository metadata"
        and entry["logger"] == "borgboi.clients.offline_storage"
        and entry["metadata_file"] == str(metadata_dir / "repo-one.json")
        for entry in entries
    )


@pytest.mark.usefixtures("create_dynamodb_table", "create_dynamodb_archives_table")
def test_dynamodb_client_logs_structured_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    from borgboi.clients.dynamodb import (
        BorgBoiArchiveTableItem,
        add_archive_to_table,
        add_repo_to_table,
        get_all_repos,
        get_archive_by_id,
    )

    repo = BorgBoiRepo(
        path="/repos/test",
        backup_target="/backup/source",
        name="repo-one",
        hostname="host-one",
        os_platform="Darwin",
        metadata=None,
    )
    archive = BorgBoiArchiveTableItem(
        repo_name="repo-one",
        iso_timestamp="2025-01-10T12:00:00",
        archive_id="archive-123",
        archive_name="2025-01-10_12:00:00",
        archive_path="/repos/test::2025-01-10_12:00:00",
        hostname="host-one",
        original_size=1000,
        compressed_size=500,
        deduped_size=250,
    )

    monkeypatch.setattr("borgboi.clients.dynamodb.borg.info", lambda repo_path, passphrase=None: None)

    add_repo_to_table(repo)
    add_archive_to_table(archive)

    repos = get_all_repos()
    archive_result = get_archive_by_id("archive-123")

    assert [saved_repo.name for saved_repo in repos] == ["repo-one"]
    assert archive_result is not None

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Adding repository to DynamoDB table"
        and entry["logger"] == "borgboi.clients.dynamodb"
        and entry["repo_name"] == "repo-one"
        for entry in entries
    )
    assert any(
        entry["event"] == "Listed repositories from DynamoDB client"
        and entry["logger"] == "borgboi.clients.dynamodb"
        and entry["repo_count"] == 1
        for entry in entries
    )
    assert any(
        entry["event"] == "Archive added to DynamoDB table"
        and entry["logger"] == "borgboi.clients.dynamodb"
        and entry["archive_name"] == "2025-01-10_12:00:00"
        for entry in entries
    )
    assert any(
        entry["event"] == "Retrieved archive from DynamoDB client by ID"
        and entry["logger"] == "borgboi.clients.dynamodb"
        and entry["archive_id"] == "archive-123"
        for entry in entries
    )


def test_borg_log_parser_logs_shape_fallback() -> None:
    cfg = Config(logging=LoggingConfig(enabled=True), debug=True)
    log_file = configure_logging(cfg)
    assert log_file is not None

    from borgboi.clients.utils.borg_logs import parse_borg_log_line

    result = parse_borg_log_line(
        '{"type": "unknown_event", "time": 1234567890.0, "levelname": "INFO", "name": "borg", "message": "Done"}'
    )

    assert isinstance(result, LogMessage)
    assert result.message == "Done"

    entries = _read_log_entries(log_file)

    assert any(
        entry["event"] == "Falling back to Borg log parsing by payload shape"
        and entry["logger"] == "borgboi.clients.utils.borg_logs"
        and entry["payload_type"] == "unknown_event"
        for entry in entries
    )
