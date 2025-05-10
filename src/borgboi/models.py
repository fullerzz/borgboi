from datetime import datetime
from functools import cached_property
from os import getenv
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

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

    @computed_field  # mypy: ignore[prop-decorator]
    @cached_property
    def safe_path(self) -> str:
        """
        Path to the Borg repository, replacing platform specific home
        directories with the current system's pattern.

        Returns:
            str: posix path to the Borg repository
        """
        if self.path.startswith("/home/"):
            child_path = self.path.split("/home/")[-1]
            path_no_username = child_path.split("/", 1)[-1]
            return (Path.home() / path_no_username).as_posix()
        elif self.path.startswith("/Users/"):
            child_path = self.path.split("/Users/")[-1]
            path_no_username = child_path.split("/", 1)[-1]
            return (Path.home() / child_path).as_posix()
        else:
            return Path(self.path).as_posix()
