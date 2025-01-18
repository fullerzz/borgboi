from pathlib import Path
from typing import Any

import pytest


@pytest.mark.usefixtures("create_dynamodb_table")
def test_create_borg_repo(repo_storage_dir: Path, backup_target_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from borgboi.orchestrator import create_borg_repo

    def mock_init_repository(*args: Any, **kwargs: Any) -> None:
        pass

    monkeypatch.setattr("borgboi.backups.BorgRepo.init_repository", mock_init_repository)
    new_repo = create_borg_repo(
        repo_storage_dir.as_posix(), backup_target_dir.as_posix(), "BORG_NEW_PASSPHRASE", "test-repo"
    )
    assert new_repo.path == repo_storage_dir
    assert new_repo.backup_target == backup_target_dir
    assert new_repo.name == "test-repo"
