"""Storage models for BorgBoi.

This module contains data models used by the storage layer,
including the S3 statistics cache.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

BYTES_PER_KB = 1024
BYTES_PER_MB = BYTES_PER_KB * 1024
BYTES_PER_GB = BYTES_PER_MB * 1024


class S3RepoStats(BaseModel):
    """S3 statistics for a single repository.

    Caches S3 usage statistics to avoid frequent API calls.

    Attributes:
        total_size_bytes: Total size of repository data in S3
        object_count: Number of objects in S3
        last_modified: When the S3 data was last modified
        cached_at: When these stats were cached
    """

    total_size_bytes: int = 0
    object_count: int = 0
    last_modified: datetime | None = None
    cached_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_size_gb(self) -> float:
        """Get total size in gigabytes."""
        return self.total_size_bytes / BYTES_PER_GB

    @property
    def total_size_formatted(self) -> str:
        """Get human-readable total size."""
        if self.total_size_bytes < BYTES_PER_KB:
            return f"{self.total_size_bytes} B"
        elif self.total_size_bytes < BYTES_PER_MB:
            return f"{self.total_size_bytes / BYTES_PER_KB:.1f} KB"
        elif self.total_size_bytes < BYTES_PER_GB:
            return f"{self.total_size_bytes / BYTES_PER_MB:.1f} MB"
        else:
            return f"{self.total_size_gb:.2f} GB"
