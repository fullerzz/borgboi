from os import environ

import boto3
from pydantic import BaseModel

from borgboi.backups import BorgRepo
from borgboi.rich_utils import console


class BorgRepoTableItem(BaseModel):
    repo_path: str
    hashed_passphrase: str


def _convert_repo_to_table_item(repo: BorgRepo) -> BorgRepoTableItem:
    """
    Convert a Borg repository to a DynamoDB table item.

    Args:
        repo (BorgRepo): Borg repository to convert

    Returns:
        BorgRepoTableItem: Borg repository converted to a DynamoDB table item
    """
    return BorgRepoTableItem(repo_path=repo.path.as_posix(), hashed_passphrase=repo.hashed_password)


def add_repo_to_table(repo: BorgRepo) -> None:
    """
    Add a Borg repository to the DynamoDB table.

    Args:
        repo (BorgRepo): Borg repository to add to the table
    """
    table = boto3.resource("dynamodb").Table(environ["BORG_DYNAMODB_TABLE"])
    table.put_item(Item=_convert_repo_to_table_item(repo).model_dump())
    console.print(f"Added repo to DynamoDB table: [bold cyan]{repo.path.as_posix()}[/]")
