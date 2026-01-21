"""Storage models for BorgBoi.

This module contains data models used by the storage layer,
including the repository index format and S3 statistics cache.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

# Size unit constants for human-readable formatting
BYTES_PER_KB = 1024
BYTES_PER_MB = BYTES_PER_KB * 1024
BYTES_PER_GB = BYTES_PER_MB * 1024


class RepositoryEntry(BaseModel):
    """Entry in the repository index.

    This is a lightweight reference to a repository stored in the index,
    containing just enough information for quick lookups without loading
    the full repository metadata.

    Attributes:
        name: Unique repository name
        path: Repository path
        hostname: Hostname of the machine
        metadata_file: Path to the full metadata file
        last_updated: When this entry was last updated
    """

    name: str
    path: str
    hostname: str
    metadata_file: str | None = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RepositoryIndex(BaseModel):
    """Index of all repositories in storage.

    The index provides fast lookups by name without loading individual
    repository metadata files.

    Attributes:
        version: Schema version for migration support
        repositories: Dictionary mapping repo names to entries
        last_updated: When the index was last modified
    """

    version: int = 1
    repositories: dict[str, RepositoryEntry] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add(self, entry: RepositoryEntry) -> None:
        """Add or update a repository entry.

        Args:
            entry: The repository entry to add
        """
        self.repositories[entry.name] = entry
        self.last_updated = datetime.now(UTC)

    def remove(self, name: str) -> RepositoryEntry | None:
        """Remove a repository entry.

        Args:
            name: The repository name to remove

        Returns:
            The removed entry, or None if not found
        """
        entry = self.repositories.pop(name, None)
        if entry:
            self.last_updated = datetime.now(UTC)
        return entry

    def get(self, name: str) -> RepositoryEntry | None:
        """Get a repository entry by name.

        Args:
            name: The repository name

        Returns:
            The entry if found, None otherwise
        """
        return self.repositories.get(name)

    def find_by_path(self, path: str, hostname: str | None = None) -> RepositoryEntry | None:
        """Find a repository entry by path.

        Args:
            path: The repository path
            hostname: Optional hostname to filter by. If None and multiple
                     repositories exist at the same path on different hosts,
                     raises ValueError.

        Returns:
            The entry if found, None otherwise

        Raises:
            ValueError: If hostname is None and multiple repositories exist
                       at the same path on different hosts
        """
        matches = [
            entry
            for entry in self.repositories.values()
            if entry.path == path and (hostname is None or entry.hostname == hostname)
        ]

        if not matches:
            return None

        if len(matches) > 1 and hostname is None:
            hostnames = [m.hostname for m in matches]
            raise ValueError(
                f"Multiple repositories found at path '{path}' on different hosts: {hostnames}. "
                "Please specify a hostname to disambiguate."
            )

        return matches[0]

    def list_names(self) -> list[str]:
        """List all repository names.

        Returns:
            List of repository names
        """
        return list(self.repositories.keys())


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


class S3StatsCache(BaseModel):
    """Cache of S3 statistics for all repositories.

    Attributes:
        version: Schema version for migration support
        repos: Dictionary mapping repo names to their S3 stats
        last_updated: When the cache was last modified
    """

    version: int = 1
    repos: dict[str, S3RepoStats] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def get(self, name: str) -> S3RepoStats | None:
        """Get S3 stats for a repository.

        Args:
            name: The repository name

        Returns:
            S3 stats if cached, None otherwise
        """
        return self.repos.get(name)

    def update(self, name: str, stats: S3RepoStats) -> None:
        """Update S3 stats for a repository.

        Args:
            name: The repository name
            stats: The S3 stats to cache
        """
        self.repos[name] = stats
        self.last_updated = datetime.now(UTC)

    def invalidate(self, name: str) -> None:
        """Invalidate cached stats for a repository.

        Args:
            name: The repository name
        """
        if name in self.repos:
            del self.repos[name]
            self.last_updated = datetime.now(UTC)

    def invalidate_all(self) -> None:
        """Invalidate all cached stats."""
        self.repos.clear()
        self.last_updated = datetime.now(UTC)
