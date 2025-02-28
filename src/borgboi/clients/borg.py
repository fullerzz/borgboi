import subprocess as sp
from collections.abc import Generator
from datetime import UTC, datetime
from functools import cached_property
from os import getenv
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field

from borgboi import rich_utils

BORGBOI_DIR_NAME = getenv("BORGBOI_DIR_NAME", ".borgboi")
EXCLUDE_FILENAME = "excludes.txt"
GIBIBYTES_IN_GIGABYTE = 0.93132257461548
STORAGE_QUOTA = "100G"


def init_repository(repo_path: str, config_additional_free_space: bool = True, json_log: bool = True) -> None:
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
    if json_log is False:
        cmd.remove("--log-json")
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


def create_archive(
    repo_path: str, repo_name: str, backup_target_path: str, archive_name: str | None = None, log_json: bool = True
) -> Generator[str]:
    """
    Create a new Borg archive of the backup target directory while yielding the output line by line.

    https://borgbackup.readthedocs.io/en/stable/usage/create.html
    """
    if not archive_name:
        archive_name = _create_archive_title()
    cmd = [
        "borg",
        "create",
        "--log-json",
        "--progress",
        "--filter",
        "AME",
        "--show-rc",
        "--list",
        "--stats",
        "--compression=zstd,1",
        "--exclude-caches",
        "--exclude-nodump",
        "--exclude-from",
        f"{(Path.home() / BORGBOI_DIR_NAME / f'{repo_name}_{EXCLUDE_FILENAME}').as_posix()}",
        f"{repo_path}::{archive_name}",
        backup_target_path,
    ]
    if log_json is False:
        cmd.remove("--log-json")

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
    archives: list[dict[str, Any]] = []


def info(repo_path: str) -> RepoInfo:
    """List a local Borg repository's info."""
    cmd = ["borg", "info", "--json", repo_path]
    result = sp.run(cmd, capture_output=True, text=True)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd, output=result.stdout, stderr=result.stderr)
    return RepoInfo.model_validate_json(result.stdout)


def prune(
    repo_path: str, keep_daily: int = 7, keep_weekly: int = 3, keep_monthly: int = 2, log_json: bool = True
) -> Generator[str]:
    """
    Run a Borg prune command to remove old backups from the repository.

    https://borgbackup.readthedocs.io/en/stable/usage/prune.html

    Args:
        keep_daily (int, optional): Number of daily backups to retain. Defaults to 7.
        keep_weekly (int, optional): Number of weekly backups to retain. Defaults to 3.
        keep_monthly (int, optional): Number of monthly backups to retain. Defaults to 2.
    """
    cmd = [
        "borg",
        "prune",
        "--log-json",
        "--progress",
        "--list",
        f"--keep-daily={keep_daily}",
        f"--keep-weekly={keep_weekly}",
        f"--keep-monthly={keep_monthly}",
        repo_path,
    ]
    if log_json is False:
        cmd.remove("--log-json")
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


def compact(repo_path: str, log_json: bool = True) -> Generator[str]:
    """
    Run a Borg compact command to free repository space.

    https://borgbackup.readthedocs.io/en/stable/usage/compact.html
    """
    cmd = [
        "borg",
        "compact",
        "--log-json",
        "--progress",
        repo_path,
    ]
    if log_json is False:
        cmd.remove("--log-json")
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


def export_repo_key(repo_path: str, repo_name: str) -> Path:
    """
    Exports the Borg repository key to a file in the user's home directory.

    https://borgbackup.readthedocs.io/en/stable/usage/key.html#borg-key-export
    """
    borgboi_repo_keys_dir = Path.home() / BORGBOI_DIR_NAME
    borgboi_repo_keys_dir.mkdir(exist_ok=True)
    key_export_path = borgboi_repo_keys_dir / f"{repo_name}-encrypted-key-backup.txt"
    cmd = ["borg", "key", "export", "--paper", repo_path, key_export_path.as_posix()]
    result = sp.run(cmd, capture_output=True, text=True)  # noqa: PLW1510, S603
    if result.returncode != 0:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd)
    return key_export_path


def extract(repo_path: str, archive_name: str, log_json: bool = True) -> Generator[str]:
    """
    Extract an archive from a Borg repository.

    https://borgbackup.readthedocs.io/en/stable/usage/extract.html
    """
    cmd = ["borg", "extract", "--log-json", "--progress", "--list", f"{repo_path}::{archive_name}"]
    if log_json is False:
        cmd.remove("--log-json")
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


def delete(repo_path: str, repo_name: str, dry_run: bool, log_json: bool = True) -> Generator[str]:
    """
    Delete the Borg repository.

    https://borgbackup.readthedocs.io/en/stable/usage/delete.html
    """
    if dry_run:
        cmd = [
            "borg",
            "delete",
            "--log-json",
            "--progress",
            "--dry-run",  # include dry-run flag
            "--list",
            "--force",
            "--checkpoint-interval",
            "10",
            repo_path,
        ]
    else:
        rich_utils.confirm_deletion(repo_name)
        cmd = [
            "borg",
            "delete",
            "--log-json",
            "--progress",
            "--list",
            "--force",
            "--checkpoint-interval",
            "10",
            repo_path,
        ]
    if log_json is False:
        cmd.remove("--log-json")
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


def delete_archive(
    repo_path: str, repo_name: str, archive_name: str, dry_run: bool, log_json: bool = True
) -> Generator[str]:
    """
    Delete an archive from the Borg repository.

    https://borgbackup.readthedocs.io/en/stable/usage/delete.html
    """
    if dry_run:
        cmd = [
            "borg",
            "delete",
            "--log-json",
            "--progress",
            "--dry-run",  # include dry-run flag
            "--list",
            "--force",
            "--checkpoint-interval",
            "10",
            f"{repo_path}::{archive_name}",
        ]
    else:
        rich_utils.confirm_deletion(repo_name, archive_name)
        cmd = [
            "borg",
            "delete",
            "--log-json",
            "--progress",
            "--list",
            "--force",
            "--checkpoint-interval",
            "10",
            f"{repo_path}::{archive_name}",
        ]
    if log_json is False:
        cmd.remove("--log-json")
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
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd, output=result.stdout, stderr=result.stderr)
    list_archives_output = ListArchivesOutput.model_validate_json(result.stdout)
    return list_archives_output.archives
