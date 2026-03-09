from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest

from borgboi.config import Config
from borgboi.core.errors import ValidationError
from borgboi.core.orchestrator import Orchestrator
from borgboi.core.output import CollectingOutputHandler
from borgboi.models import BorgBoiRepo


def _build_repo(name: str = "repo-one", hostname: str | None = None, passphrase: str | None = None) -> BorgBoiRepo:
    return BorgBoiRepo(
        path=f"/repo/{name}",
        backup_target="/backup/source",
        name=name,
        hostname=hostname or socket.gethostname(),
        os_platform="Darwin",
        metadata=None,
        passphrase=passphrase,
        passphrase_migrated=passphrase is None,
    )


@pytest.fixture
def output_handler() -> CollectingOutputHandler:
    return CollectingOutputHandler()


def test_create_repo_generates_passphrase_and_saves_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = Path("repo")
    passphrase_file = tmp_path / "repo-one.key"
    generated_passphrase = "generated-passphrase"  # noqa: S105
    storage = Mock()
    borg_client = Mock()
    borg_client.info.return_value = None
    cfg = Config(offline=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    monkeypatch.setattr("borgboi.core.orchestrator.generate_secure_passphrase", lambda: generated_passphrase)
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", lambda name, passphrase: passphrase_file)

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    orchestrator.create_repo(repo_path.as_posix(), "/backup/source", "repo-one")

    assert repo_path.exists()
    borg_client.init.assert_called_once_with(
        repo_path.as_posix(),
        passphrase=generated_passphrase,
        additional_free_space=cfg.borg.additional_free_space,
    )
    storage.save.assert_called_once()
    saved_repo = storage.save.call_args.args[0]
    assert saved_repo.name == "repo-one"
    assert saved_repo.passphrase is None
    assert saved_repo.passphrase_file_path == passphrase_file.as_posix()
    assert saved_repo.passphrase_migrated is True
    assert any("Generated passphrase for repo 'repo-one'" in message for _, message, _ in output_handler.log_messages)
    assert any(message == "SAVE THIS PASSPHRASE SECURELY!" for _, message, _ in output_handler.log_messages)


def test_create_repo_skips_free_space_for_tmp_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "tmp" / "repo"
    storage = Mock()
    borg_client = Mock()
    borg_client.info.return_value = None

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "provided-passphrase")
    monkeypatch.setattr(
        "borgboi.core.orchestrator.save_passphrase_to_file", lambda name, passphrase: tmp_path / "repo.key"
    )

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    orchestrator.create_repo(repo_path.as_posix(), "/backup/source", "repo-one")

    assert borg_client.init.call_args.kwargs["additional_free_space"] is None


def test_create_repo_rejects_file_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_file = tmp_path / "repo-file"
    repo_file.write_text("data", encoding="utf-8")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "provided-passphrase")
    monkeypatch.setattr(
        "borgboi.core.orchestrator.save_passphrase_to_file", lambda name, passphrase: tmp_path / "repo.key"
    )

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, Mock()),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="is a file"):
        orchestrator.create_repo(repo_file.as_posix(), "/backup/source", "repo-one")


def test_delete_repo_rejects_remote_repository(output_handler: CollectingOutputHandler) -> None:
    remote_repo = _build_repo(hostname="remote-host")
    storage = Mock()
    storage.get_by_name_or_path.return_value = remote_repo
    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="must be local"):
        orchestrator.delete_repo(name=remote_repo.name)


def test_delete_repo_removes_storage_and_excludes_file(
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo = _build_repo()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.delete.return_value = iter(["deleted line"])
    cfg = Config(offline=True)
    excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    excludes_path.write_text("*.tmp\n", encoding="utf-8")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "resolved-passphrase")

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    orchestrator.delete_repo(name=repo.name)

    storage.delete.assert_called_once_with(repo.name)
    assert excludes_path.exists() is False
    assert output_handler.stderr_lines == ["deleted line"]
    assert any(message == f"Deleted repository {repo.name}" for _, message, _ in output_handler.log_messages)


def test_delete_repo_dry_run_skips_storage_delete(
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo = _build_repo()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.delete.return_value = iter(["dry-run line"])

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "resolved-passphrase")

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    orchestrator.delete_repo(name=repo.name, dry_run=True)

    storage.delete.assert_not_called()


def test_daily_backup_runs_steps_and_syncs_when_enabled(output_handler: CollectingOutputHandler) -> None:
    repo = _build_repo()
    storage = Mock()
    borg_client = Mock()
    borg_client.info.return_value = {"metadata": "fresh"}
    steps: list[str] = []

    orchestrator = Orchestrator(
        config=Config(offline=False),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        s3_client=cast(Any, Mock()),
        output_handler=output_handler,
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(orchestrator, "resolve_passphrase", lambda repo_obj, cli_passphrase=None: "resolved-passphrase")
    monkeypatch.setattr(orchestrator, "backup", lambda repo_obj, passphrase=None, options=None: steps.append("backup"))
    monkeypatch.setattr(orchestrator, "prune", lambda repo_obj, passphrase=None, retention=None: steps.append("prune"))
    monkeypatch.setattr(orchestrator, "compact", lambda repo_obj, passphrase=None: steps.append("compact"))
    monkeypatch.setattr(orchestrator, "sync_to_s3", lambda repo_obj: steps.append("sync"))

    try:
        orchestrator.daily_backup(repo, sync_to_s3=True)
    finally:
        monkeypatch.undo()

    assert steps == ["backup", "prune", "compact", "sync"]
    storage.save.assert_called_once_with(repo)
    assert repo.metadata == {"metadata": "fresh"}
    assert any(message == "Daily backup completed successfully" for _, message, _ in output_handler.log_messages)


def test_delete_archive_compacts_and_refreshes_metadata(output_handler: CollectingOutputHandler) -> None:
    repo = _build_repo()
    storage = Mock()
    borg_client = Mock()
    borg_client.delete.return_value = iter(["archive deleted"])
    borg_client.info.return_value = {"metadata": "fresh"}
    resolved_passphrase = "resolved-passphrase"  # noqa: S105

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )
    compact = Mock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(orchestrator, "resolve_passphrase", lambda repo_obj, cli_passphrase=None: resolved_passphrase)
    monkeypatch.setattr(orchestrator, "compact", compact)

    try:
        orchestrator.delete_archive(repo, "archive-1")
    finally:
        monkeypatch.undo()

    compact.assert_called_once_with(repo, passphrase=resolved_passphrase)
    storage.save.assert_called_once_with(repo)
    assert repo.metadata == {"metadata": "fresh"}


def test_auto_migrate_passphrase_updates_repo_on_success(
    tmp_path: Path,
    output_handler: CollectingOutputHandler,
) -> None:
    db_passphrase = "db-passphrase"  # noqa: S105
    repo = _build_repo(passphrase=db_passphrase)
    storage = Mock()
    key_path = tmp_path / "repo-one.key"

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("borgboi.core.orchestrator.migrate_repo_passphrase", lambda name, passphrase: key_path)

    try:
        migrated_repo = orchestrator._auto_migrate_passphrase(repo)
    finally:
        monkeypatch.undo()

    assert migrated_repo.passphrase_migrated is True
    assert migrated_repo.passphrase_file_path == key_path.as_posix()
    storage.save.assert_called_once_with(migrated_repo)
    assert any(f"Passphrase migrated to {key_path}" in message for _, message, _ in output_handler.log_messages)


def test_auto_migrate_passphrase_logs_failure_without_raising(output_handler: CollectingOutputHandler) -> None:
    db_passphrase = "db-passphrase"  # noqa: S105
    repo = _build_repo(passphrase=db_passphrase)
    storage = Mock()

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "borgboi.core.orchestrator.migrate_repo_passphrase",
        lambda name, passphrase: (_ for _ in ()).throw(ValueError("bad secret")),
    )

    try:
        migrated_repo = orchestrator._auto_migrate_passphrase(repo)
    finally:
        monkeypatch.undo()

    assert migrated_repo.passphrase_migrated is False
    storage.save.assert_not_called()
    assert any(
        "Failed to auto-migrate passphrase: bad secret" in message for _, message, _ in output_handler.log_messages
    )
    assert any("migrate manually" in message for _, message, _ in output_handler.log_messages)
