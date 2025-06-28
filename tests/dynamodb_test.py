# ruff: noqa: PLC0415
from pathlib import Path
from platform import system

import pytest
from mypy_boto3_dynamodb import DynamoDBClient

from borgboi.models import BorgBoiRepo

from .conftest import DYNAMO_TABLE_NAME


def get_mock_metadata(repo_path: Path) -> str:
    """Return a mock JSON string representing a Borg repository's metadata."""
    from borgboi.clients.borg import Encryption, RepoCache, RepoInfo, Repository, Stats

    repo_info = RepoInfo(
        cache=RepoCache(
            path="/path/to/cache",
            stats=Stats(
                total_chunks=100,
                total_size=1000,
                total_csize=500,
                total_unique_chunks=50,
                unique_csize=500,
                unique_size=1000,
            ),
        ),
        encryption=Encryption(mode="repokey"),
        repository=Repository(id="1234", last_modified="2025-01-01", location=repo_path.as_posix()),
        security_dir="/path/to/security",
    )
    return repo_info.model_dump_json()


@pytest.fixture
def borgboi_repo(repo_storage_dir: Path, backup_target_dir: Path) -> BorgBoiRepo:
    from borgboi.clients.borg import RepoInfo

    metadata_json_str = get_mock_metadata(repo_storage_dir)
    return BorgBoiRepo(
        path=repo_storage_dir.as_posix(),
        backup_target=backup_target_dir.as_posix(),
        name="test-repo",
        hostname="test-host",
        os_platform=system(),
        metadata=RepoInfo.model_validate_json(metadata_json_str),
    )


@pytest.mark.usefixtures("create_dynamodb_table")
def test_add_repo_to_table(dynamodb: DynamoDBClient, borgboi_repo: BorgBoiRepo) -> None:
    from borgboi.clients.dynamodb import add_repo_to_table

    add_repo_to_table(borgboi_repo)

    response = dynamodb.get_item(TableName=DYNAMO_TABLE_NAME, Key={"repo_path": {"S": borgboi_repo.path}})
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.path  # pyright: ignore[reportTypedDictNotRequiredAccess]


@pytest.mark.usefixtures("create_dynamodb_table")
def test_update_repo(dynamodb: DynamoDBClient, borgboi_repo: BorgBoiRepo) -> None:
    from borgboi.clients.dynamodb import add_repo_to_table, get_repo_by_path, update_repo

    new_name = "updated-test-repo-name"
    new_hostname = "updated-test-hostname"

    # Populate test table with initial repo
    add_repo_to_table(borgboi_repo)
    response = dynamodb.get_item(TableName=DYNAMO_TABLE_NAME, Key={"repo_path": {"S": borgboi_repo.path}})
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.path  # pyright: ignore[reportTypedDictNotRequiredAccess]

    # Update repo fields and call update_repo(...)
    borgboi_repo.name = new_name
    borgboi_repo.hostname = new_hostname
    update_repo(borgboi_repo)

    # Verify that the repo was updated in the table
    repo_from_table = get_repo_by_path(borgboi_repo.path)
    assert repo_from_table.name == new_name
    assert repo_from_table.hostname == new_hostname
    assert repo_from_table.model_dump() == borgboi_repo.model_dump()
