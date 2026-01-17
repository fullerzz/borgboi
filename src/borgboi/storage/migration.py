"""Migration utilities for BorgBoi storage.

This module provides utilities for migrating data between different
storage formats and backends.
"""

from dataclasses import dataclass, field
from pathlib import Path

from borgboi.config import get_config
from borgboi.models import BorgBoiRepo
from borgboi.storage.base import RepositoryStorage


@dataclass
class MigrationResult:
    """Result of a storage migration operation.

    Attributes:
        repos_migrated: Number of repositories successfully migrated
        repos_skipped: Number of repositories skipped (already exist, etc.)
        errors: List of (repo_name, error_message) tuples for failed migrations
    """

    repos_migrated: int = 0
    repos_skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total number of repositories processed."""
        return self.repos_migrated + self.repos_skipped + len(self.errors)

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred."""
        return len(self.errors) > 0

    def add_error(self, repo_name: str, error_message: str) -> None:
        """Add an error to the result.

        Args:
            repo_name: Name of the repository that failed
            error_message: Description of the error
        """
        self.errors.append((repo_name, error_message))


def migrate_offline_storage(
    source_dir: Path | None = None,
    target_storage: RepositoryStorage | None = None,
    dry_run: bool = False,
) -> MigrationResult:
    """Migrate from legacy per-repo JSON storage to indexed storage.

    Legacy storage format:
        ~/.borgboi/.borgboi_metadata/{repo-name}.json

    New storage format:
        ~/.borgboi/data/repositories/{repo-name}.json
        ~/.borgboi/data/repositories_index.json

    Args:
        source_dir: Source directory containing legacy JSON files
                   (default: ~/.borgboi/.borgboi_metadata)
        target_storage: Target storage backend (default: creates new OfflineStorage)
        dry_run: If True, don't actually perform migration

    Returns:
        MigrationResult with migration statistics
    """
    from borgboi.storage.offline import OfflineStorage

    config = get_config()
    source = source_dir or config.borgboi_dir / ".borgboi_metadata"
    target = target_storage or OfflineStorage()
    result = MigrationResult()

    if not source.exists():
        return result

    for json_file in source.glob("*.json"):
        repo_name = json_file.stem

        try:
            # Load legacy repo
            content = json_file.read_text()
            repo = BorgBoiRepo.model_validate_json(content)

            # Check if already exists in target
            if target.exists(repo.name):
                result.repos_skipped += 1
                continue

            if not dry_run:
                # Save to new storage
                target.save(repo)

            result.repos_migrated += 1

        except Exception as e:
            result.add_error(repo_name, str(e))

    return result


def migrate_dynamodb_to_offline(
    source_storage: RepositoryStorage,
    target_storage: RepositoryStorage | None = None,
    dry_run: bool = False,
) -> MigrationResult:
    """Migrate repositories from DynamoDB to offline storage.

    Useful for creating local backups of cloud data or transitioning
    to offline mode.

    Args:
        source_storage: DynamoDB storage backend
        target_storage: Offline storage backend (default: creates new OfflineStorage)
        dry_run: If True, don't actually perform migration

    Returns:
        MigrationResult with migration statistics
    """
    from borgboi.storage.offline import OfflineStorage

    target = target_storage or OfflineStorage()
    result = MigrationResult()

    try:
        repos = source_storage.list_all()
    except Exception as e:
        result.add_error("__all__", f"Failed to list repositories: {e}")
        return result

    for repo in repos:
        try:
            # Check if already exists in target
            if target.exists(repo.name):
                result.repos_skipped += 1
                continue

            if not dry_run:
                target.save(repo)

            result.repos_migrated += 1

        except Exception as e:
            result.add_error(repo.name, str(e))

    return result


def migrate_offline_to_dynamodb(
    source_storage: RepositoryStorage,
    target_storage: RepositoryStorage,
    dry_run: bool = False,
) -> MigrationResult:
    """Migrate repositories from offline storage to DynamoDB.

    Useful for transitioning from offline to cloud mode.

    Args:
        source_storage: Offline storage backend
        target_storage: DynamoDB storage backend
        dry_run: If True, don't actually perform migration

    Returns:
        MigrationResult with migration statistics
    """
    result = MigrationResult()

    try:
        repos = source_storage.list_all()
    except Exception as e:
        result.add_error("__all__", f"Failed to list repositories: {e}")
        return result

    for repo in repos:
        try:
            # Check if already exists in target
            if target_storage.exists(repo.name):
                result.repos_skipped += 1
                continue

            if not dry_run:
                target_storage.save(repo)

            result.repos_migrated += 1

        except Exception as e:
            result.add_error(repo.name, str(e))

    return result


def verify_migration(
    source_storage: RepositoryStorage,
    target_storage: RepositoryStorage,
) -> tuple[list[str], list[str]]:
    """Verify that all repositories from source exist in target.

    Args:
        source_storage: Source storage backend
        target_storage: Target storage backend

    Returns:
        Tuple of (missing_repos, present_repos) lists
    """
    missing = []
    present = []

    try:
        source_repos = source_storage.list_all()
    except Exception:
        return ([], [])

    for repo in source_repos:
        if target_storage.exists(repo.name):
            present.append(repo.name)
        else:
            missing.append(repo.name)

    return (missing, present)
