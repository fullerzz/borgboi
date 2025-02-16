from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from borgboi import orchestrator
from borgboi.backups import BorgRepo
from borgboi.cli import cli
from tests.orchestrator_test import EXCLUDES_SRC


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


def test_delete_repo(repo_storage_dir: Path, borg_repo: BorgRepo) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["delete-repo", "--repo-path", str(repo_storage_dir)], input=borg_repo.name)
    assert result.exit_code == 0
    assert "Repository deleted successfully" in result.stdout
    assert "Deleted repo from DynamoDB table" in result.stdout


def test_delete_archive(repo_storage_dir: Path, borg_repo: BorgRepo) -> None:
    from borgboi.orchestrator import create_excludes_list

    # Create an exclusion list for the repo
    new_excludes_file = create_excludes_list(borg_repo.name, EXCLUDES_SRC)
    # Create an archive to be deleted in this test
    archive_name = borg_repo.create_archive()
    new_excludes_file.unlink()

    runner = CliRunner()
    deletion_confirm_input = f"{borg_repo.name}::{archive_name}"
    result = runner.invoke(
        cli,
        ["delete-archive", "--repo-path", str(repo_storage_dir), "--archive-name", archive_name],
        input=deletion_confirm_input,
    )
    assert result.exit_code == 0
    assert "Archive deleted successfully" in result.stdout
