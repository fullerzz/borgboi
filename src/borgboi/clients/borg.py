import subprocess as sp
from functools import cached_property
from os import getenv

from pydantic import BaseModel, Field, computed_field

BORGBOI_DIR_NAME = getenv("BORGBOI_DIR_NAME", ".borgboi")
EXCLUDE_FILENAME = "excludes.txt"
GIBIBYTES_IN_GIGABYTE = 0.93132257461548


class Stats(BaseModel):
    total_chunks: int
    total_csize: int = Field(description="Compressed size")
    total_size: int = Field(description="Original size")
    total_unique_chunks: int
    unique_csize: int = Field(description="Deduplicated size")
    unique_size: int


class RepoCache(BaseModel):
    path: str
    stats: Stats

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def total_size_gb(self) -> float:
        """Original size in gigabytes."""
        return self.stats.total_size / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def total_csize_gb(self) -> float:
        """Compressed size in gigabytes."""
        return self.stats.total_csize / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def unique_csize_gb(self) -> float:
        """Deduplicated size in gigabytes."""
        return self.stats.unique_csize / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE


class Encryption(BaseModel):
    mode: str


class Repository(BaseModel):
    id: str
    last_modified: str
    location: str


class RepoInfo(BaseModel):
    cache: RepoCache
    encryption: Encryption
    repository: Repository
    security_dir: str


def info(repo_path: str) -> RepoInfo:
    """List a local Borg repository's info."""
    cmd = ["borg", "info", "--json", repo_path]
    result = sp.run(cmd, capture_output=True, text=True)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd)
    return RepoInfo.model_validate_json(result.stdout)


class RepoArchive(BaseModel):
    archive: str
    id: str
    name: str
    start: str
    time: str


class ListArchivesOutput(BaseModel):
    archives: list[RepoArchive]


def list_archives(repo_path: str) -> list[RepoArchive]:
    """List the archives in a Borg repository."""
    cmd = ["borg", "list", "--json", repo_path]
    result = sp.run(cmd, capture_output=True, text=True)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd)
    list_archives_output = ListArchivesOutput.model_validate_json(result.stdout)
    return list_archives_output.archives
