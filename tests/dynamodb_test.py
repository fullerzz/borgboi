from pathlib import Path

import pytest
from mypy_boto3_dynamodb import DynamoDBClient
from pydantic import SecretStr

from borgboi.backups import BorgRepo

from .conftest import DYNAMO_TABLE_NAME


@pytest.fixture
def repo_storage_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("borgboi-test-repo")


@pytest.fixture
def borgboi_repo(repo_storage_dir: Path) -> BorgRepo:
    return BorgRepo(path=repo_storage_dir, passphrase=SecretStr("TEST"))


@pytest.mark.usefixtures("create_dynamodb_table")
def test_add_repo_to_table(dynamodb: DynamoDBClient, borgboi_repo: BorgRepo) -> None:
    from borgboi.dynamodb import add_repo_to_table

    add_repo_to_table(borgboi_repo)

    response = dynamodb.get_item(TableName=DYNAMO_TABLE_NAME, Key={"repo_path": {"S": borgboi_repo.path.as_posix()}})
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.path.as_posix()  # type: ignore
    assert response["Item"]["hashed_passphrase"]["S"] == borgboi_repo.hashed_password  # type: ignore
