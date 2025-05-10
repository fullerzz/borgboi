from datetime import datetime
from functools import cached_property
from os import getenv
from pathlib import Path

from pydantic import BaseModel, Field, computed_field, field_validator

from borgboi.clients.borg import RepoInfo

BORGBOI_DIR_NAME = getenv("BORGBOI_DIR_NAME", ".borgboi")
EXCLUDE_FILENAME = "excludes.txt"
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

    @field_validator("os_platform")
    @classmethod
    def validate_os_platform(cls, v: str) -> str:
        if v not in {"Linux", "Darwin"}:
            raise ValueError(f"os_platform must be either 'Linux' or 'Darwin'. '{v}' is not supported.")
        return v

    @computed_field  # mypy: ignore[prop-decorator]
    @cached_property
    def safe_path(self) -> str:
        """
        Path to the Borg repository, replacing platform specific home
        directories with the current system's pattern.

        Returns:
            str: posix path to the Borg repository
        """
        # FIXME: Handle scenario when username is different on the two platforms
        if self.path.startswith("/home/") and self.os_platform != "Linux":
            return self.path.replace("home/", "Users/", 1)
        elif self.path.startswith("/Users/") and self.os_platform != "Darwin":
            return self.path.replace("Users/", "home/", 1)
        else:
            return Path(self.path).as_posix()
