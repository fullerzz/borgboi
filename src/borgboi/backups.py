from datetime import UTC, datetime
from functools import cached_property
from os import environ, getenv
from pathlib import Path

from pydantic import BaseModel, SecretStr, computed_field
from pydantic.types import DirectoryPath

from borgboi import rich_utils


def _create_archive_title() -> str:
    """Returns an archive title in the format of YYYY-MM-DD_HH:MM:SS"""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")


class BorgRepo(BaseModel):
    path: DirectoryPath
    passphrase_env_var_name: str = "BORG_PASSPHRASE"  # noqa: S105
    name: str
    last_backup: datetime | None = None
    last_s3_sync: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def passphrase(self) -> SecretStr:
        return SecretStr(getenv(self.passphrase_env_var_name, ""))

    def create_archive(self, dir_to_backup: Path) -> None:
        """
        Create a new Borg archive of the specified directory.

        https://borgbackup.readthedocs.io/en/stable/usage/create.html

        Args:
            dir_to_backup (Path): directory to be used as the source for the borg archive
        """
        title = _create_archive_title()
        cmd_parts = [
            "borg",
            "create",
            "--progress",
            "--filter",
            "AME",
            "--list",
            "--stats",
            "--show-rc",
            "--compression=zstd,1",
            "--exclude-caches",
            "--exclude",
            "'home/*/.cache/*'",
            f"{self.path.as_posix()}::{title}",
            dir_to_backup.as_posix(),
        ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Creating new archive[/]",
            success_message="Archive created successfully",
            error_message="Error creating archive",
            spinner="pong",
            use_stderr=True,
        )
        self.last_backup = datetime.now(UTC)

    def prune(self, keep_daily: int = 7, keep_weekly: int = 3, keep_monthly: int = 2) -> None:
        """
        Run a Borg prune command to remove old backups from the repository.

        https://borgbackup.readthedocs.io/en/stable/usage/prune.html

        Args:
            keep_daily (int, optional): Number of daily backups to retain. Defaults to 7.
            keep_weekly (int, optional): Number of weekly backups to retain. Defaults to 3.
            keep_monthly (int, optional): Number of monthly backups to retain. Defaults to 2.
        """
        cmd_parts = [
            "borg",
            "prune",
            "--list",
            f"--keep-daily={keep_daily}",
            f"--keep-weekly={keep_weekly}",
            f"--keep-monthly={keep_monthly}",
            self.path.as_posix(),
        ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Pruning old backups[/]",
            success_message="Pruning completed successfully",
            error_message="Error pruning backups",
            spinner="dots",
            use_stderr=True,
        )

    def compact(self) -> None:
        """
        Run a Borg compact command to free repository space.

        https://borgbackup.readthedocs.io/en/stable/usage/compact.html
        """
        cmd_parts = [
            "borg",
            "compact",
            "--progress",
            self.path.as_posix(),
        ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Compacting borg repo[/]",
            success_message="Compacting completed successfully",
            error_message="Error compacting repo",
            spinner="aesthetic",
            use_stderr=True,
        )

    def sync_with_s3(self) -> None:
        sync_source = self.path.as_posix()
        s3_destination_uri = f"s3://{environ["BORG_S3_BUCKET"]}/home"
        cmd_parts = [
            "aws",
            "s3",
            "sync",
            sync_source,
            s3_destination_uri,
        ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold green]Syncing with S3 Bucket[/]",
            success_message="Successfully synced with S3 bucket",
            error_message="Error syncing with S3 bucket",
            spinner="arrow",
        )
        self.last_s3_sync = datetime.now(UTC)


def create_borg_repo(path: str, passphrase_env_var_name: str, name: str) -> BorgRepo:
    repo_path = Path(path)
    if repo_path.is_file():
        raise ValueError(f"Path {repo_path} is a file, not a directory")
    if not repo_path.exists():
        repo_path.mkdir()
    return BorgRepo(path=repo_path, passphrase_env_var_name=passphrase_env_var_name, name=name)
