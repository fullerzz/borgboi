from datetime import datetime
from os import getenv

from pydantic import BaseModel, Field

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
