"""Storage abstraction layer for BorgBoi.

This module provides a unified interface for storing and retrieving
repository metadata, supporting both offline (local) and online
(DynamoDB) storage backends.

All imports are lazy to avoid circular imports with borgboi.config.
"""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from borgboi.storage.base import RepositoryStorage
    from borgboi.storage.dynamodb import DynamoDBStorage
    from borgboi.storage.models import (
        RepositoryEntry,
        RepositoryIndex,
        S3RepoStats,
        S3StatsCache,
    )
    from borgboi.storage.offline import OfflineStorage
    from borgboi.storage.sqlite import SQLiteStorage

__all__ = [
    "DynamoDBStorage",
    "OfflineStorage",
    "RepositoryEntry",
    "RepositoryIndex",
    "RepositoryStorage",
    "S3RepoStats",
    "S3StatsCache",
    "SQLiteStorage",
]


def __getattr__(name: str) -> object:
    if name == "RepositoryStorage":
        from borgboi.storage.base import RepositoryStorage

        return RepositoryStorage
    if name == "DynamoDBStorage":
        from borgboi.storage.dynamodb import DynamoDBStorage

        return DynamoDBStorage
    if name == "OfflineStorage":
        from borgboi.storage.offline import OfflineStorage

        return OfflineStorage
    if name == "SQLiteStorage":
        from borgboi.storage.sqlite import SQLiteStorage

        return SQLiteStorage
    if name in ("RepositoryEntry", "RepositoryIndex", "S3RepoStats", "S3StatsCache"):
        from borgboi.storage import models

        return cast(object, getattr(models, name))
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
