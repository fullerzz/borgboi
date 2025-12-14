import socket
from datetime import datetime

import boto3
from botocore.config import Config
from pydantic import BaseModel

from borgboi import validator
from borgboi.clients import borg
from borgboi.config import config
from borgboi.models import BorgBoiRepo
from borgboi.rich_utils import console

boto_config = Config(retries={"mode": "standard"})


class BorgBoiArchiveTableItem(BaseModel):
    repo_name: str
    iso_timestamp: str
    archive_id: str
    archive_name: str
    archive_path: str
    hostname: str
    original_size: int
    compressed_size: int
    deduped_size: int


class BorgBoiRepoTableItem(BaseModel):
    """DynamoDB table item for a Borg repository."""

    repo_path: str
    hostname: str
    backup_target_path: str
    repo_name: str
    last_backup: str | None = None
    last_s3_sync: str | None = None
    os_platform: str | None = None
    passphrase: str | None = None
    retention_keep_daily: int | None = None
    retention_keep_weekly: int | None = None
    retention_keep_monthly: int | None = None
    retention_keep_yearly: int | None = None


def _convert_repo_to_table_item(repo: BorgBoiRepo) -> BorgBoiRepoTableItem:
    """
    Convert a Borg repository to a DynamoDB table item.

    Args:
        repo (BorgBoiRepo): Borg repository to convert

    Returns:
        BorgBoiRepoTableItem: Borg repository converted to a DynamoDB table item
    """
    return BorgBoiRepoTableItem(
        repo_path=repo.path,
        hostname=repo.hostname,
        backup_target_path=repo.backup_target,
        repo_name=repo.name,
        last_backup=repo.last_backup.isoformat() if repo.last_backup else None,
        os_platform=repo.os_platform,
    )


def _convert_table_item_to_repo(item: BorgBoiRepoTableItem) -> BorgBoiRepo:
    """
    Convert a DynamoDB table item to a Borg repository.

    Args:
        item (BorgBoiRepoTableItem): Borg repository table item to convert

    Returns:
        BorgBoiRepo: Borg repository
    """
    last_backup = datetime.fromisoformat(item.last_backup) if item.last_backup else None
    metadata = borg.info(item.repo_path) if validator.repo_is_local(item) else None

    return BorgBoiRepo(
        path=item.repo_path,
        backup_target=item.backup_target_path,
        name=item.repo_name,
        hostname=item.hostname,
        os_platform=item.os_platform or "",
        last_backup=last_backup,
        metadata=metadata,
    )


def add_repo_to_table(repo: BorgBoiRepo) -> None:
    """
    Add a Borg repository to the DynamoDB table.

    Args:
        repo (BorgBoiRepo): Borg repository to add to the table
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_repos_table)
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump(exclude_none=True))
    console.print(f"Added repo to DynamoDB table: [bold cyan]{repo.path}[/]")


def get_all_repos() -> list[BorgBoiRepo]:
    """
    Get all Borg repositories from the DynamoDB table.

    Returns:
        list[BorgBoiRepo]: List of Borg repositories
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_repos_table)
    response = table.scan()
    return [_convert_table_item_to_repo(BorgBoiRepoTableItem(**repo)) for repo in response["Items"]]  # type: ignore


def get_repo_by_path(repo_path: str, hostname: str = socket.gethostname()) -> BorgBoiRepo:
    """
    Get a Borg repository by its path from the DynamoDB table.

    Args:
        repo_path (str): Path of the Borg repository
        hostname (str): Hostname of the machine where the repo exists. Defaults to current hostname.

    Returns:
        BorgBoiRepo: Borg repository
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_repos_table)
    response = table.get_item(Key={"repo_path": repo_path, "hostname": hostname})
    return _convert_table_item_to_repo(BorgBoiRepoTableItem(**response["Item"]))  # type: ignore


def get_repo_by_name(repo_name: str) -> BorgBoiRepo:
    """
    Get a Borg repository by its name from the DynamoDB table.

    Args:
        repo_name (str): Name of the Borg repository

    Returns:
        BorgBoiRepo: Borg repository
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_repos_table)
    response = table.query(
        IndexName="name_gsi",
        KeyConditionExpression="repo_name = :name",
        ExpressionAttributeValues={":name": repo_name},
        Limit=1,
    )
    return _convert_table_item_to_repo(BorgBoiRepoTableItem(**response["Items"][0]))  # type: ignore


def delete_repo(repo: BorgBoiRepo) -> None:
    """
    Delete a Borg repository from the DynamoDB table.

    Args:
        repo (BorgBoiRepo): Borg repository to delete
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_repos_table)
    table.delete_item(Key={"repo_path": repo.path, "hostname": repo.hostname})
    console.print(f"Deleted repo from DynamoDB table: [bold cyan]{repo.path}[/]")


def update_repo(repo: BorgBoiRepo) -> None:
    """
    Update a Borg repository in the DynamoDB table.

    Args:
        repo (BorgBoiRepo): Borg repository to update
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_repos_table)
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump(exclude_none=True))
    console.print(f"Updated repo in DynamoDB table: [bold cyan]{repo.path}[/]")
