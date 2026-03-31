"""Models module for BorgBoi.

This module provides backward-compatible re-exports from the new core.models module.
The BorgBoiRepo class is now an alias for core.models.Repository.
"""

from datetime import datetime
from functools import cached_property
from pathlib import Path
from platform import system

from pydantic import BaseModel, Field, computed_field, field_validator

from borgboi.clients.borg import RepoInfo

# Re-export from core.models for new usage
from borgboi.core.models import (
    BackupOptions,
    Repository,
    RestoreOptions,
    RetentionPolicy,
)

GIBIBYTES_IN_GIGABYTE = 0.93132257461548


class BorgBoiRepo(BaseModel):
    """Contains information about a Borg repository.

    Note: This class is kept for backward compatibility.
    New code should use borgboi.core.models.Repository instead.
    """

    path: str
    backup_target: str
    name: str
    hostname: str
    os_platform: str = Field(min_length=3)
    last_backup: datetime | None = None
    metadata: RepoInfo | None

    # NEW: Retention policy and timestamps
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
        normalized = v.strip()
        normalized_lower = normalized.lower()
        if normalized_lower == "linux":
            return "Linux"
        if normalized_lower == "darwin":
            return "Darwin"
        raise ValueError(f"os_platform must be either 'Linux' or 'Darwin'. '{v}' is not supported.")

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def safe_path(self) -> str:
        """
        Path to the Borg repository, replacing platform specific home
        directories with the current system's pattern.

        Returns:
            str: posix path to the Borg repository
        """
        current_os = system()
        # FIXME: Handle scenario when username is different on the two platforms
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


# Re-export all models for convenience
__all__ = [
    "GIBIBYTES_IN_GIGABYTE",
    "BackupOptions",
    "BorgBoiRepo",
    "Repository",
    "RestoreOptions",
    "RetentionPolicy",
]
