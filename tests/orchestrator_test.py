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


@pytest.mark.usefixtures("create_dynamodb_table")
@pytest.mark.parametrize(("repo_path", "repo_name"), [(None, "test-repo"), ("/path/to/repo", None)])
def test_lookup_repo(repo_path: str | None, repo_name: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    from borgboi.orchestrator import lookup_repo

    path_func_called = False
    name_func_called = False

    def mock_get_repo_by_path(*args: Any, **kwargs: Any) -> None:
        path_func_called = True

    def mock_get_repo_by_name(*args: Any, **kwargs: Any) -> None:
        name_func_called = True

    monkeypatch.setattr("borgboi.dynamodb.get_repo_by_path", mock_get_repo_by_path)
    monkeypatch.setattr("borgboi.dynamodb.get_repo_by_name", mock_get_repo_by_path)
    lookup_repo(repo_path, repo_name)
    if repo_path:
        assert path_func_called is True
    elif repo_name:
        assert name_func_called is True
    else:
        raise AssertionError("Either get_repo_by_path or get_repo_by_name should have been called")
