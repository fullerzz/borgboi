"""Storage abstraction layer for BorgBoi.

This module provides a unified interface for storing and retrieving
repository metadata, supporting both offline (local) and online
(DynamoDB) storage backends.
"""

from borgboi.storage.base import RepositoryStorage
from borgboi.storage.dynamodb import DynamoDBStorage
from borgboi.storage.models import (
    RepositoryEntry,
    RepositoryIndex,
    S3RepoStats,
    S3StatsCache,
)
from borgboi.storage.offline import OfflineStorage

__all__ = [
    "DynamoDBStorage",
    "OfflineStorage",
    "RepositoryEntry",
    "RepositoryIndex",
    "RepositoryStorage",
    "S3RepoStats",
    "S3StatsCache",
]
