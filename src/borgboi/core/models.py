"""Core domain models for BorgBoi.

This module contains the primary data models used throughout BorgBoi,
including Repository, RetentionPolicy, and operation options.
"""

from datetime import datetime
from functools import cached_property
from pathlib import Path
from platform import system
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator

# Conversion factor for bytes to gigabytes (accounting for GiB vs GB)
GIBIBYTES_IN_GIGABYTE = 0.93132257461548


class RetentionPolicy(BaseModel):
    """Backup retention policy configuration.

    Defines how many backups to keep at each time interval.
    Values of 0 mean no backups are kept at that interval.

    Attributes:
        keep_daily: Number of daily backups to retain
        keep_weekly: Number of weekly backups to retain
        keep_monthly: Number of monthly backups to retain
        keep_yearly: Number of yearly backups to retain
    """

    keep_daily: int = Field(default=7, ge=0, description="Number of daily backups to retain")
    keep_weekly: int = Field(default=4, ge=0, description="Number of weekly backups to retain")
    keep_monthly: int = Field(default=6, ge=0, description="Number of monthly backups to retain")
    keep_yearly: int = Field(default=0, ge=0, description="Number of yearly backups to retain")

    def to_borg_args(self) -> list[str]:
        """Convert retention policy to Borg command line arguments."""
        args = [
            f"--keep-daily={self.keep_daily}",
            f"--keep-weekly={self.keep_weekly}",
            f"--keep-monthly={self.keep_monthly}",
        ]
        if self.keep_yearly > 0:
            args.append(f"--keep-yearly={self.keep_yearly}")
        return args


class BackupOptions(BaseModel):
    """Options for backup operations.

    Attributes:
        compression: Compression algorithm and level (e.g., "zstd,1", "lz4", "none")
        exclude_patterns: List of patterns to exclude from backup
        exclude_caches: Whether to exclude directories tagged as cache
        exclude_nodump: Whether to exclude files with nodump flag
        show_progress: Whether to show progress during backup
        stats: Whether to show statistics after backup
        list_files: Whether to list files being backed up
        json_output: Whether to output in JSON format
    """

    compression: str = Field(default="zstd,1", description="Compression algorithm and level")
    exclude_patterns: list[str] = Field(default_factory=list, description="Patterns to exclude from backup")
    exclude_caches: bool = Field(default=True, description="Exclude directories tagged as cache")
    exclude_nodump: bool = Field(default=True, description="Exclude files with nodump flag")
    show_progress: bool = Field(default=True, description="Show progress during backup")
    stats: bool = Field(default=True, description="Show statistics after backup")
    list_files: bool = Field(default=True, description="List files being backed up")
    json_output: bool = Field(default=True, description="Output in JSON format")

    def to_borg_args(self) -> list[str]:
        """Convert backup options to Borg command line arguments."""
        args = [f"--compression={self.compression}"]

        args.extend(f"--exclude={pattern}" for pattern in self.exclude_patterns)

        if self.exclude_caches:
            args.append("--exclude-caches")
        if self.exclude_nodump:
            args.append("--exclude-nodump")
        if self.show_progress:
            args.append("--progress")
        if self.stats:
            args.append("--stats")
        if self.list_files:
            args.append("--list")
        if self.json_output:
            args.append("--log-json")

        return args


class RestoreOptions(BaseModel):
    """Options for restore/extract operations.

    Attributes:
        dry_run: Whether to perform a dry run without extracting
        sparse: Whether to create sparse files
        include_patterns: List of patterns to include (whitelist)
        exclude_patterns: List of patterns to exclude from extraction
        strip_components: Number of leading path components to strip
        show_progress: Whether to show progress during extraction
        list_files: Whether to list files being extracted
    """

    dry_run: bool = Field(default=False, description="Perform dry run without extracting")
    sparse: bool = Field(default=False, description="Create sparse files")
    include_patterns: list[str] = Field(default_factory=list, description="Patterns to include")
    exclude_patterns: list[str] = Field(default_factory=list, description="Patterns to exclude")
    strip_components: int = Field(default=0, ge=0, description="Number of leading path components to strip")
    show_progress: bool = Field(default=True, description="Show progress during extraction")
    list_files: bool = Field(default=True, description="List files being extracted")

    def to_borg_args(self) -> list[str]:
        """Convert restore options to Borg command line arguments."""
        args = []

        if self.dry_run:
            args.append("--dry-run")
        if self.sparse:
            args.append("--sparse")
        if self.strip_components > 0:
            args.append(f"--strip-components={self.strip_components}")
        if self.show_progress:
            args.append("--progress")
        if self.list_files:
            args.append("--list")

        args.extend(f"--pattern=+{pattern}" for pattern in self.include_patterns)
        args.extend(f"--exclude={pattern}" for pattern in self.exclude_patterns)

        return args


class RepoStats(BaseModel):
    """Statistics about a Borg repository cache.

    This is compatible with the existing borg.RepoCache.stats model.
    """

    total_chunks: int
    total_csize: int = Field(description="Compressed size in bytes")
    total_size: int = Field(description="Original size in bytes")
    total_unique_chunks: int
    unique_csize: int = Field(description="Deduplicated size in bytes")
    unique_size: int


class RepoCache(BaseModel):
    """Borg repository cache information."""

    path: str
    stats: RepoStats

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def total_size_gb(self) -> str:
        """Original size in gigabytes."""
        return f"{(self.stats.total_size / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE):.2f}"

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def total_csize_gb(self) -> str:
        """Compressed size in gigabytes."""
        return f"{(self.stats.total_csize / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE):.2f}"

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def unique_csize_gb(self) -> str:
        """Deduplicated size in gigabytes."""
        return f"{(self.stats.unique_csize / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE):.2f}"


class RepoEncryption(BaseModel):
    """Borg repository encryption information."""

    mode: str


class RepoLocation(BaseModel):
    """Borg repository location information."""

    id: str
    last_modified: str
    location: str


class RepoMetadata(BaseModel):
    """Complete Borg repository metadata.

    This is compatible with the existing borg.RepoInfo model.
    """

    cache: RepoCache
    encryption: RepoEncryption
    repository: RepoLocation
    security_dir: str
    archives: list[dict[str, Any]] = Field(default_factory=list)


class Repository(BaseModel):
    """BorgBoi repository model.

    This is the core domain model for a repository, containing all
    information needed to manage backups.

    Attributes:
        path: Full path to the Borg repository
        backup_target: Path to the directory being backed up
        name: Unique name for this repository
        hostname: Hostname of the machine that created the repository
        os_platform: Operating system platform (Linux or Darwin)
        last_backup: Timestamp of the most recent backup
        metadata: Borg repository metadata (cache stats, encryption info, etc.)
        retention_policy: Backup retention policy for this repository
        last_s3_sync: Timestamp of the most recent S3 sync
        created_at: Timestamp when the repository was created
        passphrase: DEPRECATED - Passphrases are now stored in files
        passphrase_file_path: Path to file containing the passphrase
        passphrase_migrated: Whether the passphrase has been migrated to file storage
    """

    path: str
    backup_target: str
    name: str
    hostname: str
    os_platform: str = Field(min_length=3)
    last_backup: datetime | None = None
    metadata: RepoMetadata | None = None
    retention_policy: RetentionPolicy | None = None
    last_s3_sync: datetime | None = None
    created_at: datetime | None = None

    # DEPRECATED: Kept for backward compatibility
    # Passphrases are now stored in files at ~/.borgboi/passphrases/{repo-name}.key
    passphrase: str | None = None

    # NEW: File-based passphrase storage
    passphrase_file_path: str | None = None
    passphrase_migrated: bool = False

    @field_validator("os_platform")
    @classmethod
    def validate_os_platform(cls, v: str) -> str:
        if v not in {"Linux", "Darwin"}:
            raise ValueError(f"os_platform must be either 'Linux' or 'Darwin'. '{v}' is not supported.")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def safe_path(self) -> str:
        """Path to the Borg repository, with platform-specific home directory handling.

        Replaces platform-specific home directories with the current system's pattern.

        Returns:
            str: POSIX path to the Borg repository
        """
        current_os = system()
        # Handle scenario when path uses different platform's home directory
        if self.path.startswith("/home/") and current_os != "Linux":
            return self.path.replace("home/", "Users/", 1)
        elif self.path.startswith("/Users/") and current_os != "Darwin":
            return self.path.replace("Users/", "home/", 1)
        else:
            return Path(self.path).as_posix()

    def get_effective_retention(self, default: RetentionPolicy | None = None) -> RetentionPolicy:
        """Get the effective retention policy for this repository.

        Returns the repository's own retention policy if set, otherwise
        falls back to the provided default or creates a new default policy.

        Args:
            default: Default retention policy to use if repository has none

        Returns:
            RetentionPolicy: The effective retention policy
        """
        if self.retention_policy is not None:
            return self.retention_policy
        return default or RetentionPolicy()

    @property
    def has_passphrase_file(self) -> bool:
        """Check if the repository has a passphrase file configured."""
        return self.passphrase_file_path is not None and Path(self.passphrase_file_path).exists()


# Type alias for backward compatibility
BorgBoiRepo = Repository
