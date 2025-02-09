from pathlib import Path
from platform import system

import pytest
from mypy_boto3_dynamodb import DynamoDBClient

from borgboi.backups import BorgRepo

from .conftest import DYNAMO_TABLE_NAME


@pytest.fixture
def borgboi_repo(repo_storage_dir: Path, backup_target_dir: Path) -> BorgRepo:
    return BorgRepo(
        path=repo_storage_dir.as_posix(),
        backup_target=backup_target_dir.as_posix(),
        name="test-repo",
        hostname="test-host",
        os_platform=system(),
    )


@pytest.mark.usefixtures("create_dynamodb_table")
def test_add_repo_to_table(dynamodb: DynamoDBClient, borgboi_repo: BorgRepo) -> None:
    from borgboi.dynamodb import add_repo_to_table

    add_repo_to_table(borgboi_repo)

    response = dynamodb.get_item(TableName=DYNAMO_TABLE_NAME, Key={"repo_path": {"S": borgboi_repo.repo_posix_path}})
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.path  # pyright: ignore[reportTypedDictNotRequiredAccess]
    assert response["Item"]["passphrase_env_var_name"]["S"] == borgboi_repo.passphrase_env_var_name  # pyright: ignore[reportTypedDictNotRequiredAccess]


@pytest.mark.usefixtures("create_dynamodb_table")
def test_update_repo(dynamodb: DynamoDBClient, borgboi_repo: BorgRepo) -> None:
    from borgboi.dynamodb import add_repo_to_table, get_repo_by_path, update_repo

    new_name = "updated-test-repo-name"
    new_hostname = "updated-test-hostname"

    # Populate test table with initial repo
    add_repo_to_table(borgboi_repo)
    response = dynamodb.get_item(TableName=DYNAMO_TABLE_NAME, Key={"repo_path": {"S": borgboi_repo.path}})
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.repo_posix_path  # pyright: ignore[reportTypedDictNotRequiredAccess]
    assert response["Item"]["passphrase_env_var_name"]["S"] == borgboi_repo.passphrase_env_var_name  # pyright: ignore[reportTypedDictNotRequiredAccess]

    # Update repo fields and call update_repo(...)
    borgboi_repo.name = new_name
    borgboi_repo.hostname = new_hostname
    update_repo(borgboi_repo)

    # Verify that the repo was updated in the table
    repo_from_table = get_repo_by_path(borgboi_repo.repo_posix_path)
    assert repo_from_table.name == new_name
    assert repo_from_table.hostname == new_hostname
    assert repo_from_table.model_dump() == borgboi_repo.model_dump()
