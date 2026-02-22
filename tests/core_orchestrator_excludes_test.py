from pathlib import Path
from platform import system
from typing import Any, cast
from unittest.mock import Mock

import pytest

from borgboi.config import Config
from borgboi.core.errors import ValidationError
from borgboi.core.orchestrator import Orchestrator
from borgboi.models import BorgBoiRepo


def _build_repo(name: str = "test-repo") -> BorgBoiRepo:
    return BorgBoiRepo(
        path="/repo/test-repo",
        backup_target="/backup/source",
        name=name,
        hostname="localhost",
        os_platform="Darwin" if system() == "Darwin" else "Linux",
        metadata=None,
        passphrase_migrated=True,
    )


def test_backup_uses_default_shared_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = ["archive line"]

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    orchestrator.backup(repo)

    repo_specific_excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    assert not repo_specific_excludes_path.exists()
    borg_client.create.assert_called_once()
    assert borg_client.create.call_args.kwargs["exclude_file"] == default_excludes_path.as_posix()


def test_backup_prefers_repo_specific_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = ["archive line"]

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    repo_specific_excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    repo_specific_excludes_path.write_text("*.iso\n")

    orchestrator.backup(repo)

    borg_client.create.assert_called_once()
    assert borg_client.create.call_args.kwargs["exclude_file"] == repo_specific_excludes_path.as_posix()
    assert borg_client.create.call_args.kwargs["exclude_file"] != default_excludes_path.as_posix()


def test_backup_returns_created_archive_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()
    borg_client.create.return_value = ["archive line"]

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    expected_archive_name = "2026-02-22_00:02:27"
    monkeypatch.setattr(orchestrator, "_create_archive_name", lambda: expected_archive_name)

    created_archive_name = orchestrator.backup(repo)

    assert created_archive_name == expected_archive_name
    assert borg_client.create.call_args.kwargs["archive_name"] == expected_archive_name


def test_backup_raises_when_no_excludes_files_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    monkeypatch.setattr("borgboi.core.orchestrator.resolve_passphrase", lambda **_: None)
    cfg = Config(offline=True)
    borg_client = Mock()

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, borg_client),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    with pytest.raises(ValidationError, match="Exclude list must be created before performing a backup"):
        orchestrator.backup(repo)

    borg_client.create.assert_not_called()


def test_get_exclusions_uses_default_shared_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, Mock()),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n.cache/\n")

    assert orchestrator.get_exclusions(repo) == ["*.tmp", ".cache/"]


def test_get_exclusions_prefers_repo_specific_excludes_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BORGBOI_HOME", tmp_path.as_posix())
    cfg = Config(offline=True)

    orchestrator = Orchestrator(
        config=cfg,
        borg_client=cast(Any, Mock()),
        storage=cast(Any, object()),
    )
    repo = _build_repo()

    default_excludes_path = cfg.borgboi_dir / cfg.excludes_filename
    default_excludes_path.parent.mkdir(parents=True, exist_ok=True)
    default_excludes_path.write_text("*.tmp\n")

    repo_specific_excludes_path = cfg.borgboi_dir / f"{repo.name}_{cfg.excludes_filename}"
    repo_specific_excludes_path.write_text("*.iso\n")

    assert orchestrator.get_exclusions(repo) == ["*.iso"]
