import subprocess as sp
from collections.abc import Generator
from datetime import UTC, datetime
from functools import cached_property
from os import getenv
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

BORGBOI_DIR_NAME = getenv("BORGBOI_DIR_NAME", ".borgboi")
EXCLUDE_FILENAME = "excludes.txt"
GIBIBYTES_IN_GIGABYTE = 0.93132257461548
STORAGE_QUOTA = "100G"


def init_repository(repo_path: str, config_additional_free_space: bool = True) -> None:
    """
    Initialize a new Borg repository at the specified path.

    https://borgbackup.readthedocs.io/en/stable/usage/init.html
    """
    cmd = [
        "borg",
        "init",
        "--log-json",
        "--progress",
        "--encryption=repokey",
        f"--storage-quota={STORAGE_QUOTA}",
        repo_path,
    ]
    result = sp.run(cmd, capture_output=True, text=True)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd)

    if config_additional_free_space:
        config_cmd = ["borg", "config", "--log-json", "--progress", repo_path, "additional_free_space", "2G"]
        result = sp.run(config_cmd, capture_output=True, text=True)  # noqa: PLW1510, S603
        if result.returncode != 0 and result.returncode != 1:
            raise sp.CalledProcessError(returncode=result.returncode, cmd=config_cmd)


def _create_archive_title() -> str:
    """Returns an archive title in the format of YYYY-MM-DD_HH:MM:SS"""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")


def create_archive(repo_path: str, repo_name: str, backup_target_path: str) -> Generator[str]:
    """
    Create a new Borg archive of the backup target directory while yielding the output line by line.

    https://borgbackup.readthedocs.io/en/stable/usage/create.html
    """
    title = _create_archive_title()
    cmd = [
        "borg",
        "create",
        "--log-json",
        "--progress",
        "--filter",
        "AME",
        "--compression=zstd,1",
        "--exclude-caches",
        "--exclude-nodump",
        "--exclude-from",
        f"{(Path.home() / BORGBOI_DIR_NAME / f'{repo_name}_{EXCLUDE_FILENAME}').as_posix()}",
        f"{repo_path}::{title}",
        backup_target_path,
    ]

    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)  # noqa: S603
    out_stream = proc.stderr

    while out_stream.readable():  # type: ignore
        line = out_stream.readline()  # type: ignore
        if not line:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            break
        yield line.decode("utf-8")

    # stdout no longer readable so wait for return code
    returncode = proc.wait()
    if returncode != 0 and returncode != 1:
        raise sp.CalledProcessError(returncode=proc.returncode, cmd=cmd)


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
