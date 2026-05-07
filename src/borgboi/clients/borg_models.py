from datetime import datetime
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

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
    archives: list[dict[str, object]] = []


class ArchiveStats(BaseModel):
    compressed_size: int
    deduplicated_size: int
    nfiles: int
    original_size: int


class ArchiveInfo(BaseModel):
    archives: list[dict[str, object]]
    cache: RepoCache
    encryption: Encryption
    repository: Repository

    @property
    def archive(self) -> dict[str, object]:
        if not self.archives:
            raise ValueError("ArchiveInfo contains no archives.")
        return self.archives[0]


class RepoArchive(BaseModel):
    archive: str
    id: str
    name: str
    start: str
    time: str


class ListArchivesOutput(BaseModel):
    archives: list[RepoArchive]


class ArchivedFile(BaseModel):
    type: str
    mode: str
    user: str
    group: str
    uid: int
    gid: int
    path: str
    healthy: bool
    source: str
    size: int
    mtime: datetime


class DiffChange(BaseModel):
    type: str
    added: int | None = None
    removed: int | None = None
    size: int | None = None
    old: str | int | float | None = None
    new: str | int | float | None = None
    old_mode: str | None = None
    new_mode: str | None = None


class DiffEntry(BaseModel):
    path: Path
    changes: list[DiffChange] = Field(default_factory=list)


class DiffResult(BaseModel):
    archive1: str
    archive2: str
    entries: list[DiffEntry] = Field(default_factory=list)
