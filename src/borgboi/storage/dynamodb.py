"""DynamoDB storage implementation for BorgBoi.

This module provides AWS DynamoDB-backed storage for repository metadata,
used when running in cloud mode with AWS connectivity.
"""

import socket
from typing import Any, override

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config as BotoConfig
from pydantic import ValidationError

# Import the existing conversion helpers
from borgboi.clients.dynamodb import (
    BorgBoiRepoTableItem,
    _convert_repo_to_table_item,
    _convert_table_item_to_repo,
)
from borgboi.config import Config, get_config
from borgboi.core.errors import RepositoryNotFoundError, StorageError
from borgboi.core.logging import get_logger
from borgboi.models import BorgBoiRepo
from borgboi.rich_utils import console
from borgboi.storage.base import RepositoryStorage

boto_config = BotoConfig(retries={"mode": "standard"})
logger = get_logger(__name__)


class DynamoDBStorage(RepositoryStorage):
    """DynamoDB-backed storage for repository metadata.

    Stores repository metadata in AWS DynamoDB, providing cloud-based
    persistence with global secondary indexes for efficient lookups.

    Attributes:
        table_name: Name of the DynamoDB table
    """

    def __init__(self, config: Config | None = None, table_name: str | None = None) -> None:
        """Initialize DynamoDB storage.

        Args:
            config: BorgBoi configuration (default: get_config())
            table_name: DynamoDB table name (default: from config)
        """
        self._config = config or get_config()
        self.table_name = table_name or self._config.aws.dynamodb_repos_table
        self._dynamodb = boto3.resource("dynamodb", config=boto_config)

    @property
    def _table(self) -> Any:
        """Get the DynamoDB table resource."""
        return self._dynamodb.Table(self.table_name)

    # RepositoryStorage implementation

    @override
    def get(self, name: str) -> BorgBoiRepo:
        """Retrieve a repository by name."""
        logger.debug("Getting repository from DynamoDB", repo_name=name)
        try:
            response = self._table.query(
                IndexName="name_gsi",
                KeyConditionExpression=Key("repo_name").eq(name),
                Limit=1,
            )
            items = response.get("Items", [])
            if not items:
                raise RepositoryNotFoundError(f"Repository '{name}' not found", name=name)

            table_item = BorgBoiRepoTableItem.model_validate(items[0])
            return _convert_table_item_to_repo(table_item)
        except RepositoryNotFoundError:
            raise
        except ValidationError as e:
            raise StorageError(f"Invalid repository data for {name}: {e}", operation="get", cause=e) from e
        except Exception as e:
            raise StorageError(f"Failed to get repository {name}: {e}", operation="get", cause=e) from e

    @override
    def get_by_path(self, path: str, hostname: str | None = None) -> BorgBoiRepo:
        """Retrieve a repository by its path."""
        host = hostname or socket.gethostname()
        logger.debug("Getting repository from DynamoDB by path", repo_path=path, hostname=host)
        try:
            response = self._table.get_item(Key={"repo_path": path, "hostname": host})
            item = response.get("Item")
            if not item:
                raise RepositoryNotFoundError(f"Repository at path '{path}' not found", path=path)

            table_item = BorgBoiRepoTableItem.model_validate(item)
            return _convert_table_item_to_repo(table_item)
        except RepositoryNotFoundError:
            raise
        except ValidationError as e:
            raise StorageError(f"Invalid repository data at {path}: {e}", operation="get_by_path", cause=e) from e
        except Exception as e:
            raise StorageError(f"Failed to get repository at {path}: {e}", operation="get_by_path", cause=e) from e

    @override
    def list_all(self) -> list[BorgBoiRepo]:
        """List all repositories in storage."""
        logger.debug("Listing all repositories from DynamoDB", table_name=self.table_name)
        try:
            response = self._table.scan()
            repos = []
            skipped_count = 0
            for item in response.get("Items", []):
                try:
                    table_item = BorgBoiRepoTableItem.model_validate(item)
                    repos.append(_convert_table_item_to_repo(table_item))
                except ValidationError as e:
                    skipped_count += 1
                    repo_identifier = str(item.get("common_name") or item.get("repo_path") or "unknown")
                    error_count = e.error_count()
                    console.print(
                        f"[dim]Skipping repo '{repo_identifier}': invalid data in DynamoDB ({error_count} validation error(s))[/dim]"
                    )
                    logger.warning(
                        "Skipping invalid repository data from DynamoDB",
                        repo_identifier=repo_identifier,
                        validation_errors=error_count,
                    )
                    continue
                except Exception:
                    skipped_count += 1
                    repo_identifier = str(item.get("common_name") or item.get("repo_path") or "unknown")
                    console.print(f"[dim]Skipping repo '{repo_identifier}': failed to load from DynamoDB[/dim]")
                    logger.warning("Failed to load repository from DynamoDB", repo_identifier=repo_identifier)
                    continue
            logger.debug("Listed repositories from DynamoDB", repo_count=len(repos), skipped_count=skipped_count)
            return repos
        except Exception as e:
            raise StorageError(f"Failed to list repositories: {e}", operation="list_all", cause=e) from e

    @override
    def save(self, repo: BorgBoiRepo) -> None:
        """Save or update repository metadata."""
        logger.debug("Saving repository to DynamoDB", repo_name=repo.name, repo_path=repo.path)
        try:
            table_item = _convert_repo_to_table_item(repo)
            self._table.put_item(Item=table_item.model_dump(exclude_none=True))
            logger.debug("Repository saved to DynamoDB", repo_name=repo.name)
        except Exception as e:
            raise StorageError(f"Failed to save repository {repo.name}: {e}", operation="save", cause=e) from e

    @override
    def delete(self, name: str) -> None:
        """Delete a repository by name."""
        logger.debug("Deleting repository from DynamoDB", repo_name=name)
        try:
            # First get the repo to obtain path and hostname
            repo = self.get(name)
            self._table.delete_item(Key={"repo_path": repo.path, "hostname": repo.hostname})
            logger.debug("Repository deleted from DynamoDB", repo_name=name)
        except RepositoryNotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to delete repository {name}: {e}", operation="delete", cause=e) from e

    @override
    def exists(self, name: str) -> bool:
        """Check if a repository exists."""
        try:
            response = self._table.query(
                IndexName="name_gsi",
                KeyConditionExpression=Key("repo_name").eq(name),
                Limit=1,
            )
            exists_result = len(response.get("Items", [])) > 0
            logger.debug("Checking repository existence in DynamoDB", repo_name=name, exists=exists_result)
            return exists_result
        except Exception:
            return False

    def delete_by_path(self, path: str, hostname: str | None = None) -> None:
        """Delete a repository by its path.

        Args:
            path: Repository path
            hostname: Optional hostname (default: current hostname)

        Raises:
            RepositoryNotFoundError: If not found
            StorageError: If deletion fails
        """
        host = hostname or socket.gethostname()
        logger.debug("Deleting repository from DynamoDB by path", repo_path=path, hostname=host)
        try:
            # Verify it exists first
            response = self._table.get_item(Key={"repo_path": path, "hostname": host})
            if not response.get("Item"):
                raise RepositoryNotFoundError(f"Repository at path '{path}' not found", path=path)

            self._table.delete_item(Key={"repo_path": path, "hostname": host})
            logger.debug("Repository deleted from DynamoDB by path", repo_path=path, hostname=host)
        except RepositoryNotFoundError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to delete repository at {path}: {e}", operation="delete_by_path", cause=e
            ) from e
