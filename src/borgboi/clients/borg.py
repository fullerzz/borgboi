import subprocess as sp
from collections.abc import Generator
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field

from borgboi.config import config

GIBIBYTES_IN_GIGABYTE = 0.93132257461548


def _build_env_with_passphrase(passphrase: str | None = None) -> dict[str, str] | None:
    """
    Build environment dict with BORG_PASSPHRASE if passphrase provided.

    Args:
        passphrase: Optional passphrase to set in environment

    Returns:
        Environment dict with BORG_PASSPHRASE set, or None if no passphrase
    """
    if passphrase is not None:
        import os

        env = os.environ.copy()
        env["BORG_PASSPHRASE"] = passphrase
        return env
    return None


def init_repository(
    repo_path: str,
    config_additional_free_space: bool = True,
    json_log: bool = True,
    passphrase: str | None = None,
) -> None:
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
        f"--storage-quota={config.borg.storage_quota}",
        repo_path,
    ]
    if json_log is False:
        cmd.remove("--log-json")
    env = _build_env_with_passphrase(passphrase)
    result = sp.run(cmd, capture_output=True, text=True, env=env)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd)

    if config_additional_free_space:
        config_cmd = [
            "borg",
            "config",
            "--log-json",
            "--progress",
            repo_path,
            "additional_free_space",
            config.borg.additional_free_space,
        ]
        result = sp.run(config_cmd, capture_output=True, text=True, env=env)  # noqa: PLW1510, S603
        if result.returncode != 0 and result.returncode != 1:
            raise sp.CalledProcessError(returncode=result.returncode, cmd=config_cmd)


def _create_archive_title() -> str:
    """Returns an archive title in the format of YYYY-MM-DD_HH:MM:SS"""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")


def create_archive(
    repo_path: str,
    repo_name: str,
    backup_target_path: str,
    archive_name: str | None = None,
    log_json: bool = True,
    passphrase: str | None = None,
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
        f"--compression={config.borg.compression}",
        "--exclude-caches",
        "--exclude-nodump",
        "--exclude-from",
        f"{(config.borgboi_dir / f'{repo_name}_{config.excludes_filename}').as_posix()}",
        f"{repo_path}::{archive_name}",
        backup_target_path,
    ]
    if log_json is False:
        cmd.remove("--log-json")

    env = _build_env_with_passphrase(passphrase)
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603
    out_stream = proc.stderr

    while out_stream.readable():  # type: ignore[union-attr]
        line = out_stream.readline()  # type: ignore[union-attr]
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

    @computed_field  # type: ignore[prop-decorator]  # ty: ignore[unused-ignore-comment]
    @cached_property
    def total_size_gb(self) -> str:
        """Original size in gigabytes."""
        return f"{(self.stats.total_size / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE):.2f}"

    @computed_field  # type: ignore[prop-decorator]  # ty: ignore[unused-ignore-comment]
    @cached_property
    def total_csize_gb(self) -> str:
        """Compressed size in gigabytes."""
        return f"{(self.stats.total_csize / 1024 / 1024 / 1024 / GIBIBYTES_IN_GIGABYTE):.2f}"

    @computed_field  # type: ignore[prop-decorator]  # ty: ignore[unused-ignore-comment]
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


class ArchiveStats(BaseModel):
    compressed_size: int
    deduplicated_size: int
    nfiles: int
    original_size: int


class ArchiveInfo(BaseModel):
    archives: list[dict[str, Any]]
    cache: RepoCache
    encryption: Encryption
    repository: Repository

    @property
    def archive(self) -> dict[str, Any]:
        return self.archives[0]


def info(repo_path: str, passphrase: str | None = None) -> RepoInfo:
    """List a local Borg repository's info."""
    cmd = ["borg", "info", "--json", repo_path]
    env = _build_env_with_passphrase(passphrase)
    result = sp.run(cmd, capture_output=True, text=True, env=env)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd, output=result.stdout, stderr=result.stderr)
    return RepoInfo.model_validate_json(result.stdout)


def archive_info(repo_path: str, archive_name: str, passphrase: str | None = None) -> ArchiveInfo:
    """
    Get detailed information about a specific archive in a Borg repository.

    https://borgbackup.readthedocs.io/en/stable/usage/info.html

    Args:
        repo_path: Path to the Borg repository
        archive_name: Name of the archive to get info for
        passphrase: Optional passphrase for encrypted repositories

    Returns:
        ArchiveInfo object containing archive details, cache stats, encryption, and repository info
    """
    cmd = ["borg", "info", "--json", f"{repo_path}::{archive_name}"]
    env = _build_env_with_passphrase(passphrase)
    result = sp.run(cmd, capture_output=True, text=True, env=env)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd, output=result.stdout, stderr=result.stderr)
    return ArchiveInfo.model_validate_json(result.stdout)


def prune(
    repo_path: str,
    keep_daily: int | None = None,
    keep_weekly: int | None = None,
    keep_monthly: int | None = None,
    keep_yearly: int | None = None,
    log_json: bool = True,
    passphrase: str | None = None,
) -> Generator[str]:
    """
    Run a Borg prune command to remove old backups from the repository.

    https://borgbackup.readthedocs.io/en/stable/usage/prune.html

    Args:
        keep_daily: Number of daily backups to retain. Defaults to config value (7).
        keep_weekly: Number of weekly backups to retain. Defaults to config value (4).
        keep_monthly: Number of monthly backups to retain. Defaults to config value (6).
        keep_yearly: Number of yearly backups to retain. Defaults to config value (0).
    """
    # Use config defaults if not provided
    keep_daily = keep_daily if keep_daily is not None else config.borg.retention.keep_daily
    keep_weekly = keep_weekly if keep_weekly is not None else config.borg.retention.keep_weekly
    keep_monthly = keep_monthly if keep_monthly is not None else config.borg.retention.keep_monthly
    keep_yearly = keep_yearly if keep_yearly is not None else config.borg.retention.keep_yearly

    cmd = [
        "borg",
        "prune",
        "--log-json",
        "--progress",
        "--list",
        f"--keep-daily={keep_daily}",
        f"--keep-weekly={keep_weekly}",
        f"--keep-monthly={keep_monthly}",
    ]
    if keep_yearly > 0:
        cmd.append(f"--keep-yearly={keep_yearly}")

    cmd.append(repo_path)
    if log_json is False:
        cmd.remove("--log-json")
    env = _build_env_with_passphrase(passphrase)
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603
    out_stream = proc.stderr

    while out_stream.readable():  # type: ignore[union-attr]
        line = out_stream.readline()  # type: ignore[union-attr]
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


def compact(repo_path: str, log_json: bool = True, passphrase: str | None = None) -> Generator[str]:
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
    env = _build_env_with_passphrase(passphrase)
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603
    out_stream = proc.stderr

    while out_stream.readable():  # type: ignore[union-attr]
        line = out_stream.readline()  # type: ignore[union-attr]
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


def export_repo_key(repo_path: str, repo_name: str, passphrase: str | None = None) -> Path:
    """
    Exports the Borg repository key to a file in the user's home directory.

    https://borgbackup.readthedocs.io/en/stable/usage/key.html#borg-key-export
    """
    borgboi_repo_keys_dir = config.borgboi_dir
    borgboi_repo_keys_dir.mkdir(exist_ok=True)
    key_export_path = borgboi_repo_keys_dir / f"{repo_name}-encrypted-key-backup.txt"
    cmd = ["borg", "key", "export", "--paper", repo_path, key_export_path.as_posix()]
    env = _build_env_with_passphrase(passphrase)
    result = sp.run(cmd, capture_output=True, text=True, env=env)  # noqa: PLW1510, S603
    if result.returncode != 0:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd)
    return key_export_path


def extract(repo_path: str, archive_name: str, log_json: bool = True, passphrase: str | None = None) -> Generator[str]:
    """
    Extract an archive from a Borg repository.

    https://borgbackup.readthedocs.io/en/stable/usage/extract.html
    """
    cmd = ["borg", "extract", "--log-json", "--progress", "--list", f"{repo_path}::{archive_name}"]
    if log_json is False:
        cmd.remove("--log-json")
    env = _build_env_with_passphrase(passphrase)
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603
    out_stream = proc.stderr

    while out_stream.readable():  # type: ignore[union-attr]
        line = out_stream.readline()  # type: ignore[union-attr]
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


def delete(
    repo_path: str, repo_name: str, dry_run: bool, log_json: bool = True, passphrase: str | None = None
) -> Generator[str]:
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
            str(config.borg.checkpoint_interval // 90),
            repo_path,
        ]
    else:
        cmd = [
            "borg",
            "delete",
            "--log-json",
            "--progress",
            "--list",
            "--force",
            "--checkpoint-interval",
            str(config.borg.checkpoint_interval // 90),
            repo_path,
        ]
    if log_json is False:
        cmd.remove("--log-json")
    env = _build_env_with_passphrase(passphrase)
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603
    out_stream = proc.stderr

    while out_stream.readable():  # type: ignore[union-attr]
        line = out_stream.readline()  # type: ignore[union-attr]
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
    repo_path: str,
    repo_name: str,
    archive_name: str,
    dry_run: bool,
    log_json: bool = True,
    passphrase: str | None = None,
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
            str(config.borg.checkpoint_interval // 90),
            f"{repo_path}::{archive_name}",
        ]
    else:
        cmd = [
            "borg",
            "delete",
            "--log-json",
            "--progress",
            "--list",
            "--force",
            "--checkpoint-interval",
            str(config.borg.checkpoint_interval // 90),
            f"{repo_path}::{archive_name}",
        ]
    if log_json is False:
        cmd.remove("--log-json")
    env = _build_env_with_passphrase(passphrase)
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603
    out_stream = proc.stderr

    while out_stream.readable():  # type: ignore[union-attr]
        line = out_stream.readline()  # type: ignore[union-attr]
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


def list_archives(repo_path: str, passphrase: str | None = None) -> list[RepoArchive]:
    """List the archives in a Borg repository."""
    cmd = ["borg", "list", "--json", repo_path]
    env = _build_env_with_passphrase(passphrase)
    result = sp.run(cmd, capture_output=True, text=True, env=env)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd, output=result.stdout, stderr=result.stderr)
    list_archives_output = ListArchivesOutput.model_validate_json(result.stdout)
    return list_archives_output.archives


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


def list_archive_contents(
    repo_path: str, archive_name: str, json_log: bool = True, passphrase: str | None = None
) -> list[ArchivedFile]:
    """List the contents of a Borg archive."""
    cmd = ["borg", "list", f"{repo_path}::{archive_name}", "--json-lines"]
    if json_log is False:
        cmd.remove("--json-lines")
    env = _build_env_with_passphrase(passphrase)
    result = sp.run(cmd, capture_output=True, text=True, env=env)  # noqa: PLW1510, S603
    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd, output=result.stdout, stderr=result.stderr)
    return [ArchivedFile.model_validate_json(item) for item in result.stdout.splitlines() if item]
