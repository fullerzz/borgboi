from os import environ
from pathlib import Path

import boto3
from pydantic import BaseModel

from borgboi.backups import BorgRepo
from borgboi.rich_utils import console


class BorgRepoTableItem(BaseModel):
    repo_path: str
    passphrase_env_var_name: str


def _convert_repo_to_table_item(repo: BorgRepo) -> BorgRepoTableItem:
    """
    Convert a Borg repository to a DynamoDB table item.

    Args:
        repo (BorgRepo): Borg repository to convert

    Returns:
        BorgRepoTableItem: Borg repository converted to a DynamoDB table item
    """
    return BorgRepoTableItem(repo_path=repo.path.as_posix(), passphrase_env_var_name=repo.passphrase_env_var_name)


def _convert_table_item_to_repo(repo: BorgRepoTableItem) -> BorgRepo:
    """
    Convert a DynamoDB table item to a Borg repository.

    Args:
        repo (BorgRepoTableItem): Borg repository table item to convert

    Returns:
        BorgRepo: Borg repository
    """
    return BorgRepo(path=Path(repo.repo_path), passphrase_env_var_name=repo.passphrase_env_var_name)


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
