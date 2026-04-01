from __future__ import annotations

import socket
import types
from pathlib import Path
from typing import Any, cast, override
from unittest.mock import Mock

import pytest

from borgboi.clients.borg import Encryption, RepoCache, RepoInfo, Repository, Stats
from borgboi.config import Config
from borgboi.core.errors import RepositoryNotFoundError, StorageError, ValidationError
from borgboi.core.models import RetentionPolicy
from borgboi.core.orchestrator import Orchestrator
from borgboi.core.output import CollectingOutputHandler
from borgboi.lib.colors import COLOR_HEX
from borgboi.models import BorgBoiRepo


def _build_repo_info(encryption_mode: str = "repokey") -> RepoInfo:
    return RepoInfo(
        cache=RepoCache(
            path="/cache",
            stats=Stats(
                total_chunks=1,
                total_csize=1024,
                total_size=2048,
                total_unique_chunks=1,
                unique_csize=512,
                unique_size=1024,
            ),
        ),
        encryption=Encryption(mode=encryption_mode),
        repository=Repository(id="abc123", last_modified="2026-01-01T00:00:00", location="/repo"),
        security_dir="/security",
    )


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


class RecordingOutputHandler(CollectingOutputHandler):
    def __init__(self) -> None:
        super().__init__()
        self.render_calls: list[dict[str, Any]] = []

    @override
    def render_command(
        self,
        status: str,
        success_msg: str,
        log_stream: Any,
        *,
        spinner: str = "point",
        ruler_color: str = "#74c7ec",
    ) -> None:
        self.render_calls.append(
            {
                "status": status,
                "success_msg": success_msg,
                "spinner": spinner,
                "ruler_color": ruler_color,
            }
        )
        super().render_command(
            status,
            success_msg,
            log_stream,
            spinner=spinner,
            ruler_color=ruler_color,
        )


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


def test_import_repo_saves_existing_repo_metadata_and_passphrase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    passphrase_file = tmp_path / "repo-one.key"
    resolved_passphrase = "provided-passphrase"  # noqa: S105
    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    borg_client = Mock()
    borg_client.info.return_value = _build_repo_info(encryption_mode="repokey")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: resolved_passphrase)
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", lambda name, passphrase: passphrase_file)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    imported_repo = orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    storage.exists.assert_called_once_with("repo-one")
    storage.get_by_path.assert_called_once_with(repo_path.resolve().as_posix(), hostname=socket.gethostname())
    borg_client.info.assert_called_once_with(repo_path.resolve().as_posix(), passphrase=resolved_passphrase)
    storage.save.assert_called_once_with(imported_repo)
    assert imported_repo.path == repo_path.resolve().as_posix()
    assert imported_repo.backup_target == backup_target.resolve().as_posix()
    assert imported_repo.metadata is not None
    assert imported_repo.passphrase is None
    assert imported_repo.passphrase_file_path == passphrase_file.as_posix()
    assert imported_repo.passphrase_migrated is True


def test_import_repo_rejects_duplicate_name(
    tmp_path: Path,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    storage = Mock()
    storage.exists.return_value = True
    borg_client = Mock()

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="already registered"):
        orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    storage.get_by_path.assert_not_called()
    borg_client.info.assert_not_called()
    storage.save.assert_not_called()


def test_import_repo_rejects_duplicate_path(
    tmp_path: Path,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.return_value = _build_repo(name="existing-repo")
    borg_client = Mock()

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="already registered"):
        orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    borg_client.info.assert_not_called()
    storage.save.assert_not_called()


def test_import_repo_surfaces_borg_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    borg_client = Mock()
    borg_client.info.side_effect = RuntimeError("wrong passphrase")
    save_passphrase = Mock()

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "provided-passphrase")
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", save_passphrase)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="Unable to access Borg repository"):
        orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    save_passphrase.assert_not_called()
    storage.save.assert_not_called()


def test_import_repo_verifies_repokey_for_encrypted_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    passphrase_file = tmp_path / "repo-one.key"
    resolved_passphrase = "provided-passphrase"  # noqa: S105

    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    borg_client = Mock()
    borg_client.info.return_value = _build_repo_info(encryption_mode="repokey")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: resolved_passphrase)
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", lambda name, passphrase: passphrase_file)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    borg_client.export_key.assert_called_once()
    call_args = borg_client.export_key.call_args
    assert call_args.args[0] == repo_path.resolve().as_posix()
    assert call_args.kwargs["paper"] is True
    assert call_args.kwargs["passphrase"] == resolved_passphrase


def test_import_repo_rejects_inaccessible_repokey(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()

    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    borg_client = Mock()
    borg_client.info.return_value = _build_repo_info(encryption_mode="repokey")
    borg_client.export_key.side_effect = RuntimeError("key not found")
    save_passphrase = Mock()

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "provided-passphrase")
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", save_passphrase)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="Repository encryption key is not accessible"):
        orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    save_passphrase.assert_not_called()
    storage.save.assert_not_called()


def test_import_repo_skips_repokey_check_for_unencrypted_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    passphrase_file = tmp_path / "repo-one.key"

    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    borg_client = Mock()
    borg_client.info.return_value = _build_repo_info(encryption_mode="none")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", lambda name, passphrase: passphrase_file)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    borg_client.export_key.assert_not_called()


def test_import_repo_skips_passphrase_save_for_unencrypted_repo_with_ambient_passphrase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    """Regression: BORG_PASSPHRASE set for another repo must not cause a passphrase file for an unencrypted import."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    save_passphrase = Mock()

    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    borg_client = Mock()
    borg_client.info.return_value = _build_repo_info(encryption_mode="none")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "ambient-secret")
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", save_passphrase)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    imported_repo = orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    save_passphrase.assert_not_called()
    assert imported_repo.passphrase_file_path is None
    assert imported_repo.passphrase is None
    borg_client.export_key.assert_not_called()


def test_import_repo_cleans_up_passphrase_file_when_storage_save_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    passphrase_file = tmp_path / "repo-one.key"
    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    storage.save.side_effect = RuntimeError("db unavailable")
    borg_client = Mock()
    borg_client.info.return_value = _build_repo_info(encryption_mode="repokey")

    def _save_passphrase(name: str, passphrase: str) -> Path:
        del name, passphrase
        passphrase_file.write_text("secret", encoding="utf-8")
        return passphrase_file

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "provided-passphrase")
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", _save_passphrase)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(StorageError, match="Failed to save repository repo-one"):
        orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    assert passphrase_file.exists() is False


def test_import_repo_restores_existing_passphrase_file_when_storage_save_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    backup_target = tmp_path / "backup-source"
    backup_target.mkdir()
    passphrase_file = tmp_path / "repo-one.key"
    passphrase_file.write_text("original-secret", encoding="utf-8")
    passphrase_file.chmod(0o600)
    storage = Mock()
    storage.exists.return_value = False
    storage.get_by_path.side_effect = RepositoryNotFoundError("missing", path=repo_path.as_posix())
    storage.save.side_effect = RuntimeError("db unavailable")
    borg_client = Mock()
    borg_client.info.return_value = _build_repo_info(encryption_mode="repokey")

    def _save_passphrase(name: str, passphrase: str) -> Path:
        del name, passphrase
        passphrase_file.write_text("new-secret", encoding="utf-8")
        return passphrase_file

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "provided-passphrase")
    monkeypatch.setattr("borgboi.core.orchestrator.save_passphrase_to_file", _save_passphrase)
    monkeypatch.setattr("borgboi.lib.passphrase.get_passphrase_file_path", lambda repo_name: passphrase_file)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(StorageError, match="Failed to save repository repo-one"):
        orchestrator.import_repo(repo_path.as_posix(), backup_target.as_posix(), "repo-one")

    assert passphrase_file.read_text(encoding="utf-8") == "original-secret"
    assert passphrase_file.stat().st_mode & 0o777 == 0o600


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


def test_update_repo_storage_quota_updates_borg_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "segment.1").write_bytes(b"a" * 1024)
    repo = _build_repo()
    repo.path = repo_path.as_posix()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.get_additional_free_space.return_value = "0"
    resolved_passphrase = "resolved-passphrase"  # noqa: S105

    monkeypatch.setattr(
        "borgboi.core.orchestrator.shutil.disk_usage",
        lambda path: types.SimpleNamespace(total=10 * 1024**3, used=5 * 1024**3, free=5 * 1024**3),
    )
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: resolved_passphrase)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    updated_quota = orchestrator.update_repo_storage_quota("2g", name=repo.name)

    assert updated_quota == "2G"
    borg_client.get_additional_free_space.assert_called_once_with(repo.path)
    borg_client.set_storage_quota.assert_called_once_with(
        repo.path,
        "2G",
        passphrase=resolved_passphrase,
    )


def test_update_repo_storage_quota_accepts_decimal_sizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = _build_repo()
    repo.path = repo_path.as_posix()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.get_additional_free_space.return_value = "0"
    resolved_passphrase = "resolved-passphrase"  # noqa: S105

    monkeypatch.setattr(
        "borgboi.core.orchestrator.shutil.disk_usage",
        lambda path: types.SimpleNamespace(total=4 * 1024**4, used=1024**4, free=3 * 1024**4),
    )
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: resolved_passphrase)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    updated_quota = orchestrator.update_repo_storage_quota("1.5t", name=repo.name)

    assert updated_quota == "1.5T"
    borg_client.get_additional_free_space.assert_called_once_with(repo.path)
    borg_client.set_storage_quota.assert_called_once_with(
        repo.path,
        "1.5T",
        passphrase=resolved_passphrase,
    )


def test_update_repo_storage_quota_rejects_value_larger_than_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = _build_repo()
    repo.path = repo_path.as_posix()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.get_additional_free_space.return_value = "0"
    (repo_path / "segment.1").write_bytes(b"a" * 1024)

    monkeypatch.setattr(
        "borgboi.core.orchestrator.shutil.disk_usage",
        lambda path: types.SimpleNamespace(total=10 * 1024**3, used=1024**3, free=1024**3),
    )

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="cannot exceed the available disk headroom after reserved free space"):
        orchestrator.update_repo_storage_quota("2G", name=repo.name)


def test_update_repo_storage_quota_accounts_for_reserved_free_space(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    repo = _build_repo()
    repo.path = repo_path.as_posix()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.get_additional_free_space.return_value = "2G"
    config = Config(offline=True)

    monkeypatch.setattr(
        "borgboi.core.orchestrator.shutil.disk_usage",
        lambda path: types.SimpleNamespace(total=10 * 1024**3, used=0, free=10 * 1024**3),
    )
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)

    orchestrator = Orchestrator(
        config=config,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="cannot exceed the available disk headroom after reserved free space"):
        orchestrator.update_repo_storage_quota("9G", name=repo.name)


def test_update_repo_storage_quota_rejects_value_smaller_than_repo_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "segment.1").write_bytes(b"a" * 2048)
    repo = _build_repo()
    repo.path = repo_path.as_posix()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.get_additional_free_space.return_value = "0"

    monkeypatch.setattr(
        "borgboi.core.orchestrator.shutil.disk_usage",
        lambda path: types.SimpleNamespace(total=10 * 1024**3, used=0, free=0),
    )

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    with pytest.raises(ValidationError, match="cannot be smaller than the current repository size"):
        orchestrator.update_repo_storage_quota("1K", name=repo.name)


def test_get_directory_size_bytes_ignores_symlinked_directories(
    output_handler: CollectingOutputHandler, tmp_path: Path
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "segment.1").write_bytes(b"a" * 2048)

    try:
        (repo_path / "loop").symlink_to(repo_path, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable: {error}")

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, Mock()),
        output_handler=output_handler,
    )

    assert orchestrator._get_directory_size_bytes(repo_path) == 2048


def test_update_repo_storage_quota_rejects_remote_repository(output_handler: CollectingOutputHandler) -> None:
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
        orchestrator.update_repo_storage_quota("2G", name=remote_repo.name)


def test_update_repo_config_can_clear_repo_specific_quota(output_handler: CollectingOutputHandler) -> None:
    repo = _build_repo()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    passphrase_override = "override"  # noqa: S105

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    updated_quota, _ = orchestrator.update_repo_config(
        name=repo.name,
        storage_quota="",
        passphrase=passphrase_override,
    )

    borg_client.set_storage_quota.assert_called_once_with(repo.path, "0", passphrase=passphrase_override)
    assert updated_quota is None


def test_update_repo_config_does_not_create_retention_override_for_quota_only_update(
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo = _build_repo()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.set_storage_quota.return_value = iter(())

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )
    monkeypatch.setattr(orchestrator, "update_repo_storage_quota", Mock(return_value="2G"))

    updated_quota, updated_retention = orchestrator.update_repo_config(
        name=repo.name,
        storage_quota="2G",
    )

    assert updated_quota == "2G"
    assert updated_retention is None
    assert repo.retention_policy is None
    storage.save.assert_not_called()


def test_update_repo_config_can_clear_retention_override(output_handler: CollectingOutputHandler) -> None:
    repo = _build_repo()
    repo.retention_policy = RetentionPolicy(keep_daily=30, keep_weekly=8, keep_monthly=12, keep_yearly=2)
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, storage),
        output_handler=output_handler,
    )

    updated_quota, updated_retention = orchestrator.update_repo_config(
        name=repo.name,
        clear_retention_policy=True,
    )

    assert updated_quota is None
    assert updated_retention is None
    assert repo.retention_policy is None
    storage.save.assert_called_once_with(repo)


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


def test_delete_repo_can_simulate_s3_delete_during_dry_run(
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
        config=Config(offline=False),
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        s3_client=cast(Any, Mock()),
        output_handler=output_handler,
    )
    delete_from_s3 = Mock()
    monkeypatch.setattr(orchestrator, "delete_from_s3", delete_from_s3)

    orchestrator.delete_repo(name=repo.name, dry_run=True, delete_from_s3=True)

    delete_from_s3.assert_called_once_with(repo, dry_run=True)
    storage.delete.assert_not_called()


def test_delete_repo_cleans_up_local_state_when_s3_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
    output_handler: CollectingOutputHandler,
) -> None:
    repo = _build_repo()
    storage = Mock()
    storage.get_by_name_or_path.return_value = repo
    borg_client = Mock()
    borg_client.delete.return_value = iter(["deleted line"])
    cfg = Config(offline=False)
    excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    excludes_path.write_text("*.tmp\n", encoding="utf-8")

    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: "resolved-passphrase")

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, storage),
        s3_client=cast(Any, Mock()),
        output_handler=output_handler,
    )

    def raise_s3_delete_error(repo_obj: BorgBoiRepo, dry_run: bool = False) -> None:
        raise RuntimeError("s3 delete failed")

    monkeypatch.setattr(orchestrator, "delete_from_s3", raise_s3_delete_error)

    with pytest.raises(RuntimeError, match="s3 delete failed"):
        orchestrator.delete_repo(name=repo.name, delete_from_s3=True)

    storage.delete.assert_called_once_with(repo.name)
    assert excludes_path.exists() is False


def test_orchestrator_creates_default_s3_client_when_online(monkeypatch: pytest.MonkeyPatch) -> None:
    created_configs: list[object] = []

    class _FakeS3Client:
        def __init__(self, config: object) -> None:
            created_configs.append(config)

    monkeypatch.setattr("borgboi.clients.s3_client.S3Client", _FakeS3Client)

    orchestrator = Orchestrator(
        config=Config(offline=False),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, Mock()),
    )

    assert created_configs == [orchestrator.config.aws]
    assert orchestrator.s3 is not None


def test_orchestrator_skips_default_s3_client_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeS3Client:
        def __init__(self, config: object) -> None:
            raise AssertionError("S3 client should not be created in offline mode")

    monkeypatch.setattr("borgboi.clients.s3_client.S3Client", _FakeS3Client)

    orchestrator = Orchestrator(
        config=Config(offline=True),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, Mock()),
    )

    assert orchestrator.s3 is None


def test_sync_to_s3_renders_with_expected_rich_style() -> None:
    repo = _build_repo()
    storage = Mock()
    s3_client = Mock()
    s3_client.sync_to_bucket.return_value = iter(["upload line"])
    output_handler = RecordingOutputHandler()

    orchestrator = Orchestrator(
        config=Config(offline=False),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, storage),
        s3_client=cast(Any, s3_client),
        output_handler=output_handler,
    )

    orchestrator.sync_to_s3(repo)

    s3_client.sync_to_bucket.assert_called_once_with(repo.safe_path, repo.name)
    assert output_handler.render_calls == [
        {
            "status": "Syncing repo with S3 bucket",
            "success_msg": "S3 sync completed successfully",
            "spinner": "arrow",
            "ruler_color": COLOR_HEX.green,
        }
    ]
    assert output_handler.stderr_lines == ["upload line"]
    assert any(message == "S3 sync completed successfully" for _, message, _ in output_handler.log_messages)


def test_delete_from_s3_renders_with_expected_rich_style() -> None:
    repo = _build_repo()
    storage = Mock()
    s3_client = Mock()
    s3_client.delete_from_bucket.return_value = iter(["(dryrun) delete line"])
    output_handler = RecordingOutputHandler()

    orchestrator = Orchestrator(
        config=Config(offline=False),
        borg_client=cast(Any, Mock()),
        storage=cast(Any, storage),
        s3_client=cast(Any, s3_client),
        output_handler=output_handler,
    )

    orchestrator.delete_from_s3(repo, dry_run=True)

    s3_client.delete_from_bucket.assert_called_once_with(repo.name, dry_run=True)
    assert output_handler.render_calls == [
        {
            "status": "Performing dry run of S3 delete...",
            "success_msg": "S3 delete dry run completed successfully",
            "spinner": "arrow",
            "ruler_color": COLOR_HEX.red,
        }
    ]
    assert output_handler.stderr_lines == ["(dryrun) delete line"]
    assert any(message == "S3 delete dry run completed successfully" for _, message, _ in output_handler.log_messages)


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
