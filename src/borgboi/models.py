import socket
from datetime import UTC, datetime
from functools import cached_property
from os import environ, getenv
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, Field, SecretStr, computed_field, field_validator, model_validator

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
    metadata: RepoInfo
