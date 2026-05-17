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
    from borgboi.storage.models import S3RepoStats
    from borgboi.storage.sqlite import SQLiteStorage

__all__ = [
    "DynamoDBStorage",
    "RepositoryStorage",
    "S3RepoStats",
    "SQLiteStorage",
]


def __getattr__(name: str) -> object:
    if name == "RepositoryStorage":
        from borgboi.storage.base import RepositoryStorage

        return RepositoryStorage
    if name == "DynamoDBStorage":
        from borgboi.storage.dynamodb import DynamoDBStorage

        return DynamoDBStorage
    if name == "SQLiteStorage":
        from borgboi.storage.sqlite import SQLiteStorage

        return SQLiteStorage
    if name == "S3RepoStats":
        from borgboi.storage import models

        return cast(object, models.S3RepoStats)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
