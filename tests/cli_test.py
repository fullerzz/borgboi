from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from borgboi import orchestrator
from borgboi.backups import BorgRepo
from borgboi.cli import cli


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert result.stdout.startswith("Usage: cli [OPTIONS] COMMAND [ARGS]")


def test_create_repo(
    monkeypatch: pytest.MonkeyPatch, repo_storage_dir: Path, backup_target_dir: Path, borg_repo: BorgRepo
) -> None:
    def mock_create_borg_repo(*args: Any, **kwargs: Any) -> BorgRepo:
        return borg_repo

    monkeypatch.setattr(orchestrator, "create_borg_repo", mock_create_borg_repo)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["create-repo", "--repo-path", str(repo_storage_dir), "--backup-target", str(backup_target_dir)],
        input="BORG_PASSPHRASE\nTestRepo\n",
    )
    assert result.exit_code == 0
    assert "Created new Borg repo at" in result.stdout
