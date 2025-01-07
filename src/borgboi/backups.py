from os import environ
from pathlib import Path
from pydantic import BaseModel, SecretStr
from pydantic.types import DirectoryPath
from datetime import UTC, datetime
from borgboi import rich_utils


def _create_archive_title() -> str:
    """Returns an archive title in the format of YYYY-MM-DD_HH:MM:SS"""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")


class BorgRepo(BaseModel):
    path: DirectoryPath
    passphrase: SecretStr

    def create_archive(self, dir_to_backup: Path) -> None:
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

    def prune(
        self, keep_daily: int = 7, keep_weekly: int = 3, keep_monthly: int = 2
    ) -> None:
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
