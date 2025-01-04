from pathlib import Path
from pydantic import BaseModel, SecretStr
from pydantic.types import DirectoryPath
from datetime import UTC, datetime
from borgboi.rich_utils import print_cmd_parts, print_create_archive_output
import subprocess as sp


class BorgRepo(BaseModel):
    path: DirectoryPath
    passphrase: SecretStr


def _create_archive_title() -> str:
    """Returns an archive title in the format of YYYY-MM-DD_HH:MM:SS"""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")


def create_archive(repo: BorgRepo, dir_to_backup: Path) -> None:
    title = _create_archive_title()
    cmd_parts = [
        "borg",
        "create",
        "--progress",
        "--filter",
        "AME",
        "--stats",
        "--show-rc",
        "--compression=zstd,1",
        "--exclude-caches",
        "--exclude",
        "'home/*/.cache/*'",
        f"{repo.path.as_posix()}::{title}",
        dir_to_backup.as_posix(),
        "2>>",
        "/home/zach/Code/Python/borgboi/logs/borg_create_archive.log",
    ]
    print_cmd_parts(cmd_parts)

    result = sp.run(cmd_parts, capture_output=True, text=True)
    print_create_archive_output(stdout=result.stdout, stderr=result.stderr)

    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(
            returncode=result.returncode, cmd=result.args, output=result.stdout
        )


def prune(
    repo: BorgRepo, keep_daily: int = 7, keep_weekly: int = 3, keep_monthly: int = 2
) -> None:
    cmd_parts = [
        "borg",
        "prune",
        "--list",
        f"--keep-daily={keep_daily}",
        f"--keep-weekly={keep_weekly}",
        f"--keep-monthly={keep_monthly}",
        repo.path.as_posix(),
    ]
    print_cmd_parts(cmd_parts)

    result = sp.run(cmd_parts, capture_output=True, text=True)
    print_create_archive_output(stdout=result.stdout, stderr=result.stderr)

    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(
            returncode=result.returncode, cmd=result.args, output=result.stdout
        )


def compact(repo: BorgRepo) -> None:
    cmd_parts = [
        "borg",
        "compact",
        "--progress",
        repo.path.as_posix(),
    ]
    print_cmd_parts(cmd_parts)

    result = sp.run(cmd_parts, capture_output=True, text=True)
    print_create_archive_output(stdout=result.stdout, stderr=result.stderr)

    if result.returncode != 0 and result.returncode != 1:
        raise sp.CalledProcessError(
            returncode=result.returncode, cmd=result.args, output=result.stdout
        )
