import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from borgboi.backups import BorgRepo

EXCLUDES_SRC = "tests/data/excludes.txt"


@pytest.mark.usefixtures("create_dynamodb_table")
def test_create_borg_repo(repo_storage_dir: Path, backup_target_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from borgboi.orchestrator import create_borg_repo

    def mock_init_repository(*args: Any, **kwargs: Any) -> None:
        pass

    monkeypatch.setattr("borgboi.backups.BorgRepo.init_repository", mock_init_repository)
    new_repo = create_borg_repo(
        repo_storage_dir.as_posix(), backup_target_dir.as_posix(), "BORG_NEW_PASSPHRASE", "test-repo"
    )
    assert new_repo.path == repo_storage_dir.as_posix()
    assert new_repo.repo_posix_path == repo_storage_dir.as_posix()
    assert new_repo.backup_target == backup_target_dir.as_posix()
    assert new_repo.backup_target_posix_path == backup_target_dir.as_posix()
    assert new_repo.name == "test-repo"


@pytest.mark.usefixtures("create_dynamodb_table")
@pytest.mark.parametrize(("repo_path", "repo_name"), [(None, "test-repo"), ("/path/to/repo", None)])
def test_lookup_repo(repo_path: str | None, repo_name: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    import borgboi.dynamodb
    from borgboi.orchestrator import lookup_repo

    def mock_get_repo_by_path(*args: Any, **kwargs: Any) -> str:
        # Returns first arg passed into the function which is the repo path
        return args[0]

    def mock_get_repo_by_name(*args: Any, **kwargs: Any) -> None:
        # Returns first arg passed into the function which is the repo name
        return args[0]

    monkeypatch.setattr(borgboi.dynamodb, "get_repo_by_path", mock_get_repo_by_path)
    monkeypatch.setattr(borgboi.dynamodb, "get_repo_by_name", mock_get_repo_by_name)
    resp = lookup_repo(repo_path, repo_name)
    if repo_path:
        # If repo_path is provided, the mocked function should return the repo path
        assert resp == repo_path
    elif repo_name:
        # If repo_name is provided, the mocked function should return the repo name
        assert resp == repo_name
    else:
        raise AssertionError("Either get_repo_by_path or get_repo_by_name should have been called")


@pytest.mark.usefixtures("create_dynamodb_table")
def test_restore_archive(borg_repo: BorgRepo) -> None:
    # Insert a placeholder text file into the source directory
    rand_val = uuid4().hex
    file_data = {"random": rand_val}
    json_file = Path(borg_repo.backup_target) / f"data_{rand_val}.json"
    json_file_path = json_file.as_posix()
    with json_file.open("w") as f:
        json.dump(file_data, f, indent=2)
    # Create an archive of the source directory
    archive_name = borg_repo.create_archive()
    # delete data.json
    json_file.unlink()
    assert json_file.exists() is False
    # extract the archive into the test dir
    borg_repo.extract(archive_name)
    # Assert that the placeholder text file is present in the restore directory
    restored_file = Path(f"{Path.cwd().as_posix()}/{json_file_path}")
    assert restored_file.exists()
    with restored_file.open("r") as f:
        restored_data = json.load(f)
    assert restored_data == file_data


def test_create_excludes_list(borg_repo_without_excludes: BorgRepo) -> None:
    from borgboi.backups import BORGBOI_DIR_NAME, EXCLUDE_FILENAME
    from borgboi.orchestrator import create_excludes_list

    borg_repo = borg_repo_without_excludes
    # Create an exclusion list for the repo
    create_excludes_list(borg_repo.name, EXCLUDES_SRC)
    # Assert that the exclusion list was created
    new_exclusions_list = Path.home() / BORGBOI_DIR_NAME / f"{borg_repo.name}_{EXCLUDE_FILENAME}"
    assert new_exclusions_list.exists() is True

    with Path(EXCLUDES_SRC).open("r") as f:
        expected_excludes = f.read()
    with (Path.home() / BORGBOI_DIR_NAME / f"{borg_repo.name}_{EXCLUDE_FILENAME}").open("r") as f:
        actual_excludes = f.read()
    assert actual_excludes == expected_excludes
    new_exclusions_list.unlink()
