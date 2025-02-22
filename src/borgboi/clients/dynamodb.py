from datetime import datetime
from os import environ

import boto3
from botocore.config import Config
from pydantic import BaseModel

from borgboi.backups import BorgRepo
from borgboi.rich_utils import console

boto_config = Config(retries={"mode": "standard"})


class BorgRepoTableItem(BaseModel):
    repo_path: str
    backup_target_path: str
    passphrase_env_var_name: str
    common_name: str
    hostname: str
    os_platform: str
    last_backup: str | None = None
    last_s3_sync: str | None = None
    total_size_gb: str = "0.0"
    total_csize_gb: str = "0.0"
    unique_csize_gb: str = "0.0"


def _convert_repo_to_table_item(repo: BorgRepo) -> BorgRepoTableItem:
    """
    Convert a Borg repository to a DynamoDB table item.

    Args:
        repo (BorgRepo): Borg repository to convert

    Returns:
        BorgRepoTableItem: Borg repository converted to a DynamoDB table item
    """
    if repo.metadata is None:
        size_metadata = {
            "total_size_gb": "0.0",
            "total_csize_gb": "0.0",
            "unique_csize_gb": "0.0",
        }
    else:
        size_metadata = {
            "total_size_gb": f"{repo.metadata.cache.total_size_gb:.2f}",
            "total_csize_gb": f"{repo.metadata.cache.total_csize_gb:.2f}",
            "unique_csize_gb": f"{repo.metadata.cache.unique_csize_gb:.2f}",
        }

    return BorgRepoTableItem(
        repo_path=repo.path,
        backup_target_path=repo.backup_target,
        passphrase_env_var_name=repo.passphrase_env_var_name,
        common_name=repo.name,
        hostname=repo.hostname,
        os_platform=repo.os_platform,
        last_backup=repo.last_backup.isoformat() if repo.last_backup else None,
        last_s3_sync=repo.last_s3_sync.isoformat() if repo.last_s3_sync else None,
        **size_metadata,
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
        path=repo.repo_path,
        backup_target=repo.backup_target_path,
        passphrase_env_var_name=repo.passphrase_env_var_name,
        name=repo.common_name,
        hostname=repo.hostname,
        os_platform=repo.os_platform,
        last_backup=last_backup,
        last_s3_sync=last_s3_sync,
        total_size_gb=float(repo.total_size_gb),
        total_csize_gb=float(repo.total_csize_gb),
        unique_csize_gb=float(repo.unique_csize_gb),
    )


def add_repo_to_table(repo: BorgRepo) -> None:
    """
    Add a Borg repository to the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to add to the table
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump())
    console.print(f"Added repo to DynamoDB table: [bold cyan]{repo.repo_posix_path}[/]")


def get_all_repos() -> list[BorgRepo]:
    """
    Get all Borg repositories from the DynamoDB table.

    Returns:
        list[BorgRepo]: List of Borg repositories
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
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
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
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
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    response = table.query(
        IndexName="name_gsi",
        KeyConditionExpression="common_name = :name",
        ExpressionAttributeValues={":name": repo_name},
        Limit=1,
    )
    return _convert_table_item_to_repo(BorgRepoTableItem(**response["Items"][0]))  # type: ignore


def delete_repo(repo: BorgRepo) -> None:
    """
    Delete a Borg repository from the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to delete
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    table.delete_item(Key={"repo_path": repo.path})
    console.print(f"Deleted repo from DynamoDB table: [bold cyan]{repo.repo_posix_path}[/]")


def update_repo(repo: BorgRepo) -> None:
    """
    Update a Borg repository in the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to update
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump())
    console.print(f"Updated repo in DynamoDB table: [bold cyan]{repo.repo_posix_path}[/]")
