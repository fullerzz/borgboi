from datetime import datetime
from functools import cached_property
from pathlib import Path
from platform import system

from pydantic import BaseModel, Field, computed_field, field_validator

from borgboi.clients.borg import RepoInfo

GIBIBYTES_IN_GIGABYTE = 0.93132257461548


class BorgBoiRepo(BaseModel):
    """Contains information about a Borg repository."""

    path: str
    backup_target: str
    name: str
    hostname: str
    os_platform: str = Field(min_length=3)
    last_backup: datetime | None = None
    metadata: RepoInfo | None

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
