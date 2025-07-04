import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from borgboi.models import BorgBoiRepo

EXCLUDES_SRC = "tests/data/excludes.txt"


@pytest.mark.usefixtures("create_dynamodb_table")
@pytest.mark.parametrize("offline_mode", [True, False])
def test_create_borg_repo(repo_storage_dir: Path, backup_target_dir: Path, offline_mode: bool) -> None:
    from borgboi.orchestrator import create_borg_repo

    new_repo = create_borg_repo(
        repo_storage_dir.as_posix(), backup_target_dir.as_posix(), "test-repo", offline=offline_mode
    )
    assert new_repo.path == repo_storage_dir.as_posix()
    assert new_repo.backup_target == backup_target_dir.as_posix()
    assert new_repo.name == "test-repo"


def test_create_borg_repo_offline_metadata(tmp_path: Path, backup_target_dir: Path) -> None:
    """
    Test that creating a repo in offline mode stores metadata in the offline metadata directory.
    """
    from borgboi.clients.offline_storage import METADATA_DIR
    from borgboi.orchestrator import create_borg_repo

    repo_storage_dir = tmp_path / "offline_repo"
    repo_storage_dir.mkdir()
    repo_name = "offline-test-repo"
    offline = True

    new_repo = create_borg_repo(repo_storage_dir.as_posix(), backup_target_dir.as_posix(), repo_name, offline=offline)
    assert new_repo.path == repo_storage_dir.as_posix()
    assert new_repo.backup_target == backup_target_dir.as_posix()
    assert new_repo.name == repo_name

    # Validate the offline metadata file is created
    metadata_dir = METADATA_DIR
    metadata_file = metadata_dir / f"{repo_name}.json"
    assert metadata_file.exists(), f"Offline metadata file {metadata_file} was not created"
    with metadata_file.open("r") as f:
        borgboi_repo = BorgBoiRepo.model_validate_json(f.read())
        assert borgboi_repo.name == repo_name


@pytest.mark.usefixtures("create_dynamodb_table")
@pytest.mark.parametrize(("repo_path", "repo_name"), [(None, "test-repo"), ("/path/to/repo", None)])
def test_lookup_repo(repo_path: str | None, repo_name: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    import borgboi.clients.dynamodb
    from borgboi.orchestrator import lookup_repo

    def mock_get_repo_by_path(*args: Any, **kwargs: Any) -> str:
        # Returns first arg passed into the function which is the repo path
        return args[0]

    def mock_get_repo_by_name(*args: Any, **kwargs: Any) -> None:
        # Returns first arg passed into the function which is the repo name
        return args[0]

    monkeypatch.setattr(borgboi.clients.dynamodb, "get_repo_by_path", mock_get_repo_by_path)
    monkeypatch.setattr(borgboi.clients.dynamodb, "get_repo_by_name", mock_get_repo_by_name)
    resp = lookup_repo(repo_path, repo_name, False)
    if repo_path:
        # If repo_path is provided, the mocked function should return the repo path
        assert resp == repo_path
    elif repo_name:
        # If repo_name is provided, the mocked function should return the repo name
        assert resp == repo_name
    else:
        raise AssertionError("Either get_repo_by_path or get_repo_by_name should have been called")


# TODO: Implement test_lookup_repo_offline(...) to test the offline mode of lookup_repo


@pytest.mark.usefixtures("create_dynamodb_table")
def test_restore_archive(borg_repo: BorgBoiRepo) -> None:
    from borgboi.clients import borg

    # Insert a placeholder text file into the source directory
    rand_val = uuid4().hex
    file_data = {"random": rand_val}
    json_file = Path(borg_repo.backup_target) / f"data_{rand_val}.json"
    json_file_path = json_file.as_posix()
    with json_file.open("w") as f:
        json.dump(file_data, f, indent=2)
    # Create an archive of the source directory
    archive_name = borg._create_archive_title()
    for _ in borg.create_archive(borg_repo.path, borg_repo.name, borg_repo.backup_target, archive_name):
        pass
    # delete data.json
    json_file.unlink()
    assert json_file.exists() is False
    # extract the archive into the test dir
    for _ in borg.extract(borg_repo.path, archive_name):
        pass
    # Assert that the placeholder text file is present in the restore directory
    restored_file = Path(f"{Path.cwd().as_posix()}/{json_file_path}")
    assert restored_file.exists()
    with restored_file.open("r") as f:
        restored_data = json.load(f)
    assert restored_data == file_data


def test_create_excludes_list(borg_repo_without_excludes: BorgBoiRepo) -> None:
    from borgboi.models import BORGBOI_DIR_NAME, EXCLUDE_FILENAME
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


def test_delete_repo_no_exclusions_list(borg_repo_without_excludes: BorgBoiRepo) -> None:
    from borgboi.orchestrator import delete_borg_repo

    repo = borg_repo_without_excludes
    delete_borg_repo(repo.path, repo.name, False, False)
    # This test passes if no exception is raised


@pytest.mark.usefixtures("create_dynamodb_table")
def test_get_excludes_file(borg_repo: BorgBoiRepo) -> None:
    from borgboi.orchestrator import get_excludes_file

    repo_name = borg_repo.name
    excludes_file = get_excludes_file(repo_name, False)
    assert excludes_file is not None
    assert excludes_file.exists() is True


@pytest.mark.usefixtures("create_dynamodb_table")
def test_append_to_excludes_file(borg_repo: BorgBoiRepo) -> None:
    from borgboi.orchestrator import append_to_excludes_file, get_excludes_file

    new_excludes_line = "foo/*"

    excludes_file = get_excludes_file(borg_repo.name, False)
    assert excludes_file.exists() is True
    with excludes_file.open("r") as f:
        excludes_content = f.readlines()
    original_line_count = len(excludes_content)
    # Verify that the new_excludes_line is not already in the excludes file
    for line in excludes_content:
        assert line != new_excludes_line

    # Append new_excludes_line to the excludes file
    append_to_excludes_file(excludes_file, new_excludes_line)
    with excludes_file.open("r") as f:
        excludes = f.readlines()
    new_line_count = len(excludes)
    assert new_line_count == original_line_count + 1
    assert excludes[-1].rstrip("\r\n") == new_excludes_line


@pytest.mark.usefixtures("create_dynamodb_table")
def test_remove_from_excludes_file(borg_repo: BorgBoiRepo) -> None:
    from borgboi.orchestrator import get_excludes_file, remove_from_excludes_file

    excludes_file = get_excludes_file(borg_repo.name, False)
    assert excludes_file.exists() is True
    # Get line count from the original excludes file
    with excludes_file.open("r") as f:
        excludes_content = f.readlines()
    original_line_count = len(excludes_content)

    # Create dict of line_number: line_content
    line_dict = {line_num: line for line_num, line in enumerate(excludes_content)}
    # Remove line 2 from the excludes file
    index_to_remove = 2

    remove_from_excludes_file(excludes_file, index_to_remove)

    with excludes_file.open("r") as f:
        excludes = f.readlines()
    new_line_count = len(excludes)
    assert new_line_count == original_line_count - 1
    updated_line_dict = {line_num: line for line_num, line in enumerate(excludes)}
    assert updated_line_dict[index_to_remove] != line_dict[index_to_remove]
