import os
from collections.abc import Generator
from typing import Any

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_dynamodb import DynamoDBClient
from mypy_boto3_s3 import S3Client

DYNAMO_TABLE_NAME = "borg-repos-test"


@pytest.fixture(autouse=True)
def _common_env_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BORG_PASSPHRASE", "test")
    monkeypatch.setenv("BORG_S3_BUCKET", "test")
    monkeypatch.setenv("BORG_DYNAMODB_TABLE", DYNAMO_TABLE_NAME)


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
def mocked_aws(aws_credentials: None) -> Generator[None, Any, None]:
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
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    )
    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=DYNAMO_TABLE_NAME, WaiterConfig={"Delay": 2, "MaxAttempts": 10})
