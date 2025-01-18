from datetime import datetime
from os import environ
from pathlib import Path

import boto3
from pydantic import BaseModel

from borgboi.backups import BorgRepo
from borgboi.rich_utils import console


class BorgRepoTableItem(BaseModel):
    repo_path: str
    backup_target_path: str
    passphrase_env_var_name: str
    common_name: str
    hostname: str
    last_backup: str | None = None
    last_s3_sync: str | None = None


def _convert_repo_to_table_item(repo: BorgRepo) -> BorgRepoTableItem:
    """
    Convert a Borg repository to a DynamoDB table item.

    Args:
        repo (BorgRepo): Borg repository to convert

    Returns:
        BorgRepoTableItem: Borg repository converted to a DynamoDB table item
    """
    return BorgRepoTableItem(
        repo_path=repo.path.as_posix(),
        backup_target_path=repo.backup_target.as_posix(),
        passphrase_env_var_name=repo.passphrase_env_var_name,
        common_name=repo.name,
        hostname=repo.hostname,
        last_backup=repo.last_backup.isoformat() if repo.last_backup else None,
        last_s3_sync=repo.last_s3_sync.isoformat() if repo.last_s3_sync else None,
    )


def _convert_table_item_to_repo(repo: BorgRepoTableItem) -> BorgRepo:
    """
    Convert a DynamoDB table item to a Borg repository.

    Args:
        repo (BorgRepoTableItem): Borg repository table item to convert

    Returns:
        BorgRepo: Borg repository
    """
    last_backup = None
    last_s3_sync = None
    if repo.last_backup:
        last_backup = datetime.fromisoformat(repo.last_backup)
    if repo.last_s3_sync:
        last_s3_sync = datetime.fromisoformat(repo.last_s3_sync)

    return BorgRepo(
        path=Path(repo.repo_path),
        backup_target=Path(repo.backup_target_path),
        passphrase_env_var_name=repo.passphrase_env_var_name,
        name=repo.common_name,
        hostname=repo.hostname,
        last_backup=last_backup,
        last_s3_sync=last_s3_sync,
    )


def add_repo_to_table(repo: BorgRepo) -> None:
    """
    Add a Borg repository to the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to add to the table
    """
    table = boto3.resource("dynamodb").Table(environ["BORG_DYNAMODB_TABLE"])
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump())
    console.print(f"Added repo to DynamoDB table: [bold cyan]{repo.path.as_posix()}[/]")


def get_all_repos() -> list[BorgRepo]:
    """
    Get all Borg repositories from the DynamoDB table.

    Returns:
        list[BorgRepo]: List of Borg repositories
    """
    table = boto3.resource("dynamodb").Table(environ["BORG_DYNAMODB_TABLE"])
    response = table.scan()
    return [_convert_table_item_to_repo(BorgRepoTableItem(**repo)) for repo in response["Items"]]  # type: ignore


def get_repo_by_path(repo_path: str) -> BorgRepo:
    """
    Get a Borg repository by its path from the DynamoDB table.

    Args:
        repo_path (str): Path of the Borg repository

    Returns:
        BorgRepo: Borg repository
    """
    table = boto3.resource("dynamodb").Table(environ["BORG_DYNAMODB_TABLE"])
    response = table.get_item(Key={"repo_path": repo_path})
    return _convert_table_item_to_repo(BorgRepoTableItem(**response["Item"]))  # type: ignore


def get_repo_by_name(repo_name: str) -> BorgRepo:
    """
    Get a Borg repository by its name from the DynamoDB table.

    Args:
        repo_name (str): Name of the Borg repository

    Returns:
        BorgRepo: Borg repository
    """
    table = boto3.resource("dynamodb").Table(environ["BORG_DYNAMODB_TABLE"])
    response = table.query(
        IndexName="name_gsi",
        KeyConditionExpression="common_name = :name",
        ExpressionAttributeValues={":name": repo_name},
        Limit=1,
    )
    return _convert_table_item_to_repo(BorgRepoTableItem(**response["Items"][0]))  # type: ignore


def update_repo(repo: BorgRepo) -> None:
    """
    Update a Borg repository in the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to update
    """
    table = boto3.resource("dynamodb").Table(environ["BORG_DYNAMODB_TABLE"])
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump())
    console.print(f"Updated repo in DynamoDB table: [bold cyan]{repo.path.as_posix()}[/]")
