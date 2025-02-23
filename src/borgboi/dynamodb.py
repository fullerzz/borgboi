from datetime import datetime
from os import environ

import boto3
from botocore.config import Config
from pydantic import BaseModel

from borgboi import validator
from borgboi.clients import borg
from borgboi.clients.borg import RepoInfo
from borgboi.models import BorgBoiRepo
from borgboi.rich_utils import console

boto_config = Config(retries={"mode": "standard"})


class BorgRepoTableItem(BaseModel):
    repo_path: str
    backup_target_path: str
    common_name: str
    hostname: str
    os_platform: str
    last_backup: str | None = None
    metadata: RepoInfo | None = None


def _convert_repo_to_table_item(repo: BorgBoiRepo) -> BorgRepoTableItem:
    """
    Convert a Borg repository to a DynamoDB table item.

    Args:
        repo (BorgBoiRepo): Borg repository to convert

    Returns:
        BorgRepoTableItem: Borg repository converted to a DynamoDB table item
    """
    if not validator.metadata_is_present(repo):
        raise ValueError("The 'metadata' field must be present in the BorgBoiRepo object")

    return BorgRepoTableItem(
        repo_path=repo.path,
        backup_target_path=repo.backup_target,
        common_name=repo.name,
        hostname=repo.hostname,
        os_platform=repo.os_platform,
        last_backup=repo.last_backup.isoformat() if repo.last_backup else None,
        metadata=repo.metadata,
    )


def _convert_table_item_to_repo(repo: BorgRepoTableItem) -> BorgBoiRepo:
    """
    Convert a DynamoDB table item to a Borg repository.

    Args:
        repo (BorgRepoTableItem): Borg repository table item to convert

    Returns:
        BorgRepo: Borg repository
    """
    last_backup = None
    if repo.last_backup:
        last_backup = datetime.fromisoformat(repo.last_backup)

    metadata = repo.metadata if repo.metadata else borg.info(repo.repo_path)

    return BorgBoiRepo(
        path=repo.repo_path,
        backup_target=repo.backup_target_path,
        name=repo.common_name,
        hostname=repo.hostname,
        os_platform=repo.os_platform,
        last_backup=last_backup,
        metadata=metadata,
    )


def add_repo_to_table(repo: BorgBoiRepo) -> None:
    """
    Add a Borg repository to the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to add to the table
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump())
    console.print(f"Added repo to DynamoDB table: [bold cyan]{repo.path}[/]")


def get_all_repos() -> list[BorgBoiRepo]:
    """
    Get all Borg repositories from the DynamoDB table.

    Returns:
        list[BorgBoiRepo]: List of Borg repositories
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    response = table.scan()
    return [_convert_table_item_to_repo(BorgRepoTableItem(**repo)) for repo in response["Items"]]  # type: ignore


def get_repo_by_path(repo_path: str) -> BorgBoiRepo:
    """
    Get a Borg repository by its path from the DynamoDB table.

    Args:
        repo_path (str): Path of the Borg repository

    Returns:
        BorgBoiRepo: Borg repository
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    response = table.get_item(Key={"repo_path": repo_path})
    return _convert_table_item_to_repo(BorgRepoTableItem(**response["Item"]))  # type: ignore


def get_repo_by_name(repo_name: str) -> BorgBoiRepo:
    """
    Get a Borg repository by its name from the DynamoDB table.

    Args:
        repo_name (str): Name of the Borg repository

    Returns:
        BorgBoiRepo: Borg repository
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    response = table.query(
        IndexName="name_gsi",
        KeyConditionExpression="common_name = :name",
        ExpressionAttributeValues={":name": repo_name},
        Limit=1,
    )
    return _convert_table_item_to_repo(BorgRepoTableItem(**response["Items"][0]))  # type: ignore


def delete_repo(repo: BorgBoiRepo) -> None:
    """
    Delete a Borg repository from the DynamoDB table.

    Args:
        repo (BorgBoiRepo): Borg repository to delete
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    table.delete_item(Key={"repo_path": repo.path})
    console.print(f"Deleted repo from DynamoDB table: [bold cyan]{repo.path}[/]")


def update_repo(repo: BorgBoiRepo) -> None:
    """
    Update a Borg repository in the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to update
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(environ["BORG_DYNAMODB_TABLE"])
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump())
    console.print(f"Updated repo in DynamoDB table: [bold cyan]{repo.path}[/]")
