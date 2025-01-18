from pathlib import Path

import pytest
from mypy_boto3_dynamodb import DynamoDBClient

from borgboi.backups import BorgRepo

from .conftest import DYNAMO_TABLE_NAME


@pytest.fixture
def repo_storage_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("borgboi-test-repo")


@pytest.fixture
def backup_target_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("borgboi-test-backup-target")


@pytest.fixture
def borgboi_repo(repo_storage_dir: Path, backup_target_dir: Path) -> BorgRepo:
    return BorgRepo(path=repo_storage_dir, backup_target=backup_target_dir, name="test-repo", hostname="test-host")


@pytest.mark.usefixtures("create_dynamodb_table")
def test_add_repo_to_table(dynamodb: DynamoDBClient, borgboi_repo: BorgRepo) -> None:
    from borgboi.dynamodb import add_repo_to_table

    add_repo_to_table(borgboi_repo)

    response = dynamodb.get_item(TableName=DYNAMO_TABLE_NAME, Key={"repo_path": {"S": borgboi_repo.path.as_posix()}})
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.path.as_posix()  # pyright: ignore[reportTypedDictNotRequiredAccess]
    assert response["Item"]["passphrase_env_var_name"]["S"] == borgboi_repo.passphrase_env_var_name  # pyright: ignore[reportTypedDictNotRequiredAccess]
