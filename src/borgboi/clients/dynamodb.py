import socket
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rich.pretty import pprint

from borgboi import validator
from borgboi.clients import borg
from borgboi.config import config
from borgboi.lib.passphrase import resolve_passphrase
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

    model_config = ConfigDict(populate_by_name=True)

    repo_path: str
    hostname: str
    backup_target_path: str
    repo_name: str = Field(..., alias="common_name")
    last_backup: str | None = None
    last_s3_sync: str | None = None
    os_platform: str | None = None

    # DEPRECATED: Kept for backward compatibility
    passphrase: str | None = None

    # NEW: File-based passphrase storage
    passphrase_file_path: str | None = None
    passphrase_migrated: bool | None = None

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
    data = {
        "repo_path": repo.path,
        "hostname": repo.hostname,
        "backup_target_path": repo.backup_target,
        "common_name": repo.name,
        "os_platform": repo.os_platform,
        "passphrase": repo.passphrase,
        "passphrase_file_path": repo.passphrase_file_path,
        "passphrase_migrated": repo.passphrase_migrated,
    }
    if repo.last_backup:
        data["last_backup"] = repo.last_backup.isoformat()
    return BorgBoiRepoTableItem.model_validate(data)


def _convert_table_item_to_repo(item: BorgBoiRepoTableItem) -> BorgBoiRepo:
    """
    Convert a DynamoDB table item to a Borg repository.

    Args:
        item (BorgBoiRepoTableItem): Borg repository table item to convert

    Returns:
        BorgBoiRepo: Borg repository
    """
    last_backup = datetime.fromisoformat(item.last_backup) if item.last_backup else None

    # Resolve passphrase for local repos before getting metadata
    metadata = None
    if validator.repo_is_local(item):
        passphrase = resolve_passphrase(
            repo_name=item.repo_name,
            cli_passphrase=None,
            db_passphrase=item.passphrase,
            allow_env_fallback=True,
        )
        metadata = borg.info(item.repo_path, passphrase=passphrase)

    return BorgBoiRepo(
        path=item.repo_path,
        backup_target=item.backup_target_path,
        name=item.repo_name,
        hostname=item.hostname,
        os_platform=item.os_platform or "",
        last_backup=last_backup,
        metadata=metadata,
        passphrase=item.passphrase,
        passphrase_file_path=item.passphrase_file_path,
        passphrase_migrated=item.passphrase_migrated or False,
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
    db_repo_items: list[BorgBoiRepoTableItem] = []
    for repo in response["Items"]:
        pprint(repo)
        try:
            db_repo_items.append(BorgBoiRepoTableItem.model_validate(repo))
        except ValidationError as e:
            repo_identifier = str(repo.get("common_name") or repo.get("repo_path") or "unknown")
            error_count = e.error_count()
            console.print(
                f"[dim]Skipping repo '{repo_identifier}': invalid data in DynamoDB ({error_count} validation error(s))[/dim]"
            )
            continue
    return [_convert_table_item_to_repo(repo) for repo in db_repo_items]


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
    return _convert_table_item_to_repo(BorgBoiRepoTableItem.model_validate(response.get("Item")))


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
        KeyConditionExpression=Key("repo_name").eq(repo_name),
        Limit=1,
    )
    return _convert_table_item_to_repo(BorgBoiRepoTableItem.model_validate(response["Items"][0]))


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


# ============================================================================
# Archive Table Operations
# ============================================================================


def add_archive_to_table(item: BorgBoiArchiveTableItem) -> None:
    """
    Add a Borg archive to the DynamoDB archives table.

    Args:
        item: Archive metadata to add to the table
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_archives_table)
    table.put_item(Item=item.model_dump(exclude_none=True))
    console.print(f"Added archive to DynamoDB table: [bold cyan]{item.archive_name}[/]")


def get_archives_by_repo(repo_name: str) -> list[BorgBoiArchiveTableItem]:
    """
    Get all archives for a specific repository from the DynamoDB table.

    Args:
        repo_name: Name of the Borg repository

    Returns:
        List of archive metadata items
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_archives_table)
    response = table.query(
        KeyConditionExpression=Key("repo_name").eq(repo_name),
    )
    return [BorgBoiArchiveTableItem.model_validate(item) for item in response.get("Items", [])]


def get_archive_by_id(archive_id: str) -> BorgBoiArchiveTableItem | None:
    """
    Get a specific archive by its ID from the DynamoDB table.

    Args:
        archive_id: The archive ID (from Borg)

    Returns:
        Archive metadata if found, None otherwise
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_archives_table)
    response = table.query(
        IndexName="archive_id_gsi",
        KeyConditionExpression=Key("archive_id").eq(archive_id),
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return None
    return BorgBoiArchiveTableItem.model_validate(items[0])


def get_archives_by_hostname(hostname: str) -> list[BorgBoiArchiveTableItem]:
    """
    Get all archives for a specific hostname from the DynamoDB table.

    Args:
        hostname: Hostname to filter by

    Returns:
        List of archive metadata items
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_archives_table)
    response = table.query(
        IndexName="hostname_gsi",
        KeyConditionExpression=Key("hostname").eq(hostname),
    )
    return [BorgBoiArchiveTableItem.model_validate(item) for item in response.get("Items", [])]


def delete_archive(repo_name: str, iso_timestamp: str) -> None:
    """
    Delete an archive from the DynamoDB archives table.

    Args:
        repo_name: Name of the Borg repository
        iso_timestamp: ISO timestamp of the archive (sort key)
    """
    table = boto3.resource("dynamodb", config=boto_config).Table(config.aws.dynamodb_archives_table)
    table.delete_item(Key={"repo_name": repo_name, "iso_timestamp": iso_timestamp})
    console.print(f"Deleted archive from DynamoDB table: [bold cyan]{repo_name}::{iso_timestamp}[/]")


def build_archive_table_item(
    repo: BorgBoiRepo,
    archive_name: str,
    passphrase: str | None = None,
) -> BorgBoiArchiveTableItem:
    """
    Build a BorgBoiArchiveTableItem from available borg data.

    This function retrieves archive details using `borg info` and constructs
    the table item with all required fields.

    Args:
        repo: The BorgBoiRepo containing repository information
        archive_name: Name of the archive to get info for
        passphrase: Optional passphrase for encrypted repositories

    Returns:
        Populated archive table item ready for DynamoDB
    """
    archive_info = borg.archive_info(repo.path, archive_name, passphrase)
    archive_data = archive_info.archive

    # Parse the timestamp from archive_name (format: YYYY-MM-DD_HH:MM:SS)
    # Convert to ISO format for the sort key
    iso_timestamp = datetime.strptime(archive_name, "%Y-%m-%d_%H:%M:%S").isoformat()

    return BorgBoiArchiveTableItem(
        repo_name=repo.name,
        iso_timestamp=iso_timestamp,
        archive_id=archive_data.get("id", ""),
        archive_name=archive_name,
        archive_path=f"{repo.path}::{archive_name}",
        hostname=archive_data.get("hostname", socket.gethostname()),
        original_size=archive_data.get("stats", {}).get("original_size", 0),
        compressed_size=archive_data.get("stats", {}).get("compressed_size", 0),
        deduped_size=archive_data.get("stats", {}).get("deduplicated_size", 0),
    )
