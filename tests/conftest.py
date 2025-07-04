import os
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_dynamodb import DynamoDBClient
from mypy_boto3_s3 import S3Client

from borgboi.models import BorgBoiRepo
from tests.orchestrator_test import EXCLUDES_SRC

DYNAMO_TABLE_NAME = "borg-repos-test"


def _cleanup_borg_security_files(repo_id: str, security_dir: str) -> None:
    """Clean up borg security files for a test repository."""
    try:
        # Clean up files in the security directory that match the repo id
        security_path = Path(security_dir)
        if security_path.exists():
            # Look for files that contain the repo id
            for file_path in security_path.iterdir():
                if file_path.is_file() and repo_id in file_path.parts:
                    file_path.unlink(missing_ok=True)
            security_path.rmdir()
    except Exception:
        warnings.warn(f"Failed to cleanup borg security files for repo {repo_id} in {security_dir}", stacklevel=2)


@pytest.fixture(autouse=True)
def _common_env_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BORG_PASSPHRASE", "test")
    monkeypatch.setenv("BORG_NEW_PASSPHRASE", "test")
    monkeypatch.setenv("BORG_S3_BUCKET", "test")
    monkeypatch.setenv("BORG_DYNAMODB_TABLE", DYNAMO_TABLE_NAME)
    monkeypatch.setenv("BORGBOI_DIR_NAME", ".borgboi")


@pytest.fixture
def aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_SECURITY_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_SESSION_TOKEN"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = "us-west-1"


@pytest.fixture
def s3(aws_credentials: None) -> Generator[S3Client]:
    """
    Return a mocked S3 client
    """
    with mock_aws():
        yield boto3.client("s3", region_name="us-west-1")


@pytest.fixture
def dynamodb(aws_credentials: None) -> Generator[DynamoDBClient]:
    """
    Return a mocked S3 client
    """
    with mock_aws():
        yield boto3.client("dynamodb", region_name="us-west-1")


@pytest.fixture
def mocked_aws(aws_credentials: None) -> Generator[None, Any]:
    """
    Mock all AWS interactions
    Requires you to create your own boto3 clients
    """
    with mock_aws():
        yield


@pytest.fixture
def create_dynamodb_table(dynamodb: DynamoDBClient) -> None:
    dynamodb.create_table(
        TableName=DYNAMO_TABLE_NAME,
        KeySchema=[
            {"AttributeName": "repo_path", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "repo_path", "AttributeType": "S"},
            {"AttributeName": "common_name", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
        GlobalSecondaryIndexes=[
            {
                "IndexName": "name_gsi",
                "KeySchema": [
                    {"AttributeName": "common_name", "KeyType": "HASH"},
                ],
                "Projection": {
                    "ProjectionType": "ALL",
                },
                "ProvisionedThroughput": {"ReadCapacityUnits": 123, "WriteCapacityUnits": 123},
                "OnDemandThroughput": {"MaxReadRequestUnits": 123, "MaxWriteRequestUnits": 123},
                "WarmThroughput": {"ReadUnitsPerSecond": 123, "WriteUnitsPerSecond": 123},
            },
        ],
    )
    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=DYNAMO_TABLE_NAME, WaiterConfig={"Delay": 2, "MaxAttempts": 10})


@pytest.fixture
def repo_storage_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("borgboi-test-repo")


@pytest.fixture
def backup_target_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("borgboi-test-backup-target")


@pytest.fixture
def borg_repo(repo_storage_dir: Path, backup_target_dir: Path, create_dynamodb_table: None) -> Generator[BorgBoiRepo]:
    """
    Provides a BorgRepo with an excludes list already created.
    """
    from borgboi.orchestrator import create_borg_repo, create_excludes_list

    repo_name = uuid4().hex[0:5]
    repo = create_borg_repo(repo_storage_dir.as_posix(), backup_target_dir.as_posix(), repo_name, offline=False)
    exclusion_list = create_excludes_list(repo_name, EXCLUDES_SRC)
    yield repo
    exclusion_list.unlink(missing_ok=True)
    # Clean up borg security files
    if repo.metadata and repo.metadata.repository and repo.metadata.repository.id:
        _cleanup_borg_security_files(repo.metadata.repository.id, repo.metadata.security_dir)


@pytest.fixture
def borg_repo_without_excludes(
    repo_storage_dir: Path, backup_target_dir: Path, create_dynamodb_table: None
) -> Generator[BorgBoiRepo]:
    """
    Provides a BorgRepo without an excludes list already created.
    """
    from borgboi.orchestrator import create_borg_repo

    repo_name = uuid4().hex[0:5]
    repo = create_borg_repo(repo_storage_dir.as_posix(), backup_target_dir.as_posix(), repo_name, False)
    yield repo
    # Clean up borg security files
    if repo.metadata and repo.metadata.repository and repo.metadata.repository.id:
        _cleanup_borg_security_files(repo.metadata.repository.id, repo.metadata.security_dir)
