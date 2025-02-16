import socket
import subprocess as sp
from datetime import UTC, datetime
from functools import cached_property
from os import environ, getenv
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, SecretStr, computed_field, field_validator, model_validator

from borgboi import rich_utils

BORGBOI_DIR_NAME = getenv("BORGBOI_DIR_NAME", ".borgboi")
EXCLUDE_FILENAME = "excludes.txt"
GIBIBYTES_IN_GIGABYTE = 0.93132257461548


def _create_archive_title() -> str:
    """Returns an archive title in the format of YYYY-MM-DD_HH:MM:SS"""
    return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")


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


class BorgRepo(BaseModel):
    path: str
    backup_target: str
    passphrase_env_var_name: str = "BORG_PASSPHRASE"  # noqa: S105
    name: str
    hostname: str
    last_backup: datetime | None = None
    last_s3_sync: datetime | None = None
    metadata: RepoInfo | None = None
    os_platform: str = Field(min_length=3)
    total_size_gb: float = 0.0
    total_csize_gb: float = 0.0
    unique_csize_gb: float = 0.0

    @field_validator("os_platform", mode="after")
    @classmethod
    def _validate_os_platform(cls, v: str) -> str:
        if v not in {"Darwin", "Linux"}:
            raise ValueError("os_platform must be either 'Darwin' or 'Linux'")
        return v

    @model_validator(mode="after")
    def _validate_dirs_exist(self) -> Self:
        """
        Validates the repo and backup target dirs exist if repo is local.
        """
        if self.hostname == socket.gethostname():
            repo_path = Path(self.path)
            if repo_path.exists() is False:
                raise ValueError("Repository path does not exist")
            elif repo_path.is_dir() is False:
                raise ValueError("Repository path is not a directory")
            backup_path = Path(self.backup_target)
            if backup_path.exists() is False:
                raise ValueError("Backup target path does not exist")
            elif backup_path.is_dir() is False:
                raise ValueError("Backup target path is not a directory")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def passphrase(self) -> SecretStr:
        return SecretStr(getenv(self.passphrase_env_var_name, ""))

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def repo_posix_path(self) -> str:
        """
        Borg repo path in POSIX format.
        """
        return Path(self.path).as_posix()

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def backup_target_posix_path(self) -> str:
        """
        Borg backup target path in POSIX format.
        """
        return Path(self.backup_target).as_posix()

    def init_repository(self, config_additional_free_space: bool = True) -> None:
        """
        Initialize a new Borg repository at the specified path.

        https://borgbackup.readthedocs.io/en/stable/usage/init.html
        """
        cmd_parts = [
            "borg",
            "init",
            "--progress",
            "--encryption=repokey",
            "--storage-quota=100G",
            self.repo_posix_path,
        ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Initializing new repository[/]",
            success_message="Repository initialized successfully",
            error_message="Error initializing repository",
            spinner="arc",
            use_stderr=True,
        )

        if config_additional_free_space:
            config_cmd_parts = ["borg", "config", self.repo_posix_path, "additional_free_space", "2G"]
            rich_utils.run_and_log_sp_popen(
                cmd_parts=config_cmd_parts,
                status_message="[bold blue]Configuring additional_free_space[/]",
                success_message="Configuration applied successfully",
                error_message="Error configuration additional_free_space",
                spinner="arc",
                use_stderr=True,
            )

    def create_archive(self) -> str:
        """
        Create a new Borg archive of the backup target directory.

        https://borgbackup.readthedocs.io/en/stable/usage/create.html
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
            "--exclude-nodump",
            "--exclude-from",
            f"{(Path.home() / BORGBOI_DIR_NAME / f'{self.name}_{EXCLUDE_FILENAME}').as_posix()}",
            f"{self.repo_posix_path}::{title}",
            self.backup_target_posix_path,
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
        return title

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
            self.repo_posix_path,
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
            self.repo_posix_path,
        ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Compacting borg repo[/]",
            success_message="Compacting completed successfully",
            error_message="Error compacting repo",
            spinner="aesthetic",
            use_stderr=True,
        )

    def info(self) -> None:
        """
        Run a Borg info command to display information about the repository.

        https://borgbackup.readthedocs.io/en/stable/usage/info.html
        """
        cmd_parts = ["borg", "info", self.repo_posix_path]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Getting repo info[/]",
            success_message="Repo info retrieved successfully",
            error_message="Error getting repo info",
            spinner="triangle",
            use_stderr=False,
        )

    def collect_json_info(self) -> None:
        """
        Run a Borg info command with the '--json' option to collect
        information about the repository in JSON format for programmatic use.

        If successful, this function produces no output to the console.

        https://borgbackup.readthedocs.io/en/stable/usage/info.html
        """
        cmd_parts = ["borg", "info", "--json", self.repo_posix_path]
        rich_utils.print_cmd_parts(cmd_parts)

        result = sp.run(cmd_parts, capture_output=True, text=True)  # noqa: PLW1510, S603
        if result.returncode != 0 and result.returncode != 1:
            raise sp.CalledProcessError(returncode=result.returncode, cmd=cmd_parts)
        self.metadata = RepoInfo.model_validate_json(result.stdout)

    def export_repo_key(self) -> None:
        """
        Exports the Borg repository key to a file in the user's home directory.

        https://borgbackup.readthedocs.io/en/stable/usage/key.html#borg-key-export
        """
        borgboi_repo_keys_dir = Path.home() / BORGBOI_DIR_NAME
        borgboi_repo_keys_dir.mkdir(exist_ok=True)
        key_export_path = borgboi_repo_keys_dir / f"{self.name}-encrypted-key-backup.txt"
        cmd_parts = ["borg", "key", "export", "--paper", self.repo_posix_path, key_export_path.as_posix()]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Exporting repo key[/]",
            success_message=f"Repo key exported successfully to {key_export_path.as_posix()}",
            error_message="Error exporting repo key",
            spinner="aesthetic",
            use_stderr=True,
        )

    def extract(self, archive_name: str) -> None:
        """
        Extract the contents of a Borg archive into the current working directory.

        https://borgbackup.readthedocs.io/en/stable/usage/extract.html
        """
        cmd_parts = [
            "borg",
            "extract",
            "-v",
            "--progress",
            "--list",
            f"{self.repo_posix_path}::{archive_name}",
        ]
        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Extracting archive[/]",
            success_message=f"Extracted archive successfully to {Path.cwd().as_posix()}",
            error_message="Error extracting archive",
            spinner="point",
            use_stderr=True,
        )

    def delete(self, dry_run: bool) -> None:
        """
        Delete the Borg repository.

        https://borgbackup.readthedocs.io/en/stable/usage/delete.html
        """
        if dry_run:
            cmd_parts = [
                "borg",
                "delete",
                "-v",
                "--dry-run",  # include dry-run flag
                "--list",
                "--force",
                "--checkpoint-interval",
                "10",
                self.repo_posix_path,
            ]
        else:
            rich_utils.confirm_deletion(self.name)
            cmd_parts = [
                "borg",
                "delete",
                "-v",
                "--list",
                "--force",
                "--checkpoint-interval",
                "10",
                self.repo_posix_path,
            ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Deleting repository[/]",
            success_message="Repository deleted successfully",
            error_message="Error deleting repository",
            spinner="dots",
            use_stderr=True,
        )

    def delete_archive(self, archive_name: str, dry_run: bool) -> None:
        """
        Delete an archive from the Borg repository.

        https://borgbackup.readthedocs.io/en/stable/usage/delete.html
        """
        if dry_run:
            cmd_parts = [
                "borg",
                "delete",
                "-v",
                "--dry-run",  # include dry-run flag
                "--list",
                "--force",
                "--checkpoint-interval",
                "10",
                f"{self.repo_posix_path}::{archive_name}",
            ]
        else:
            rich_utils.confirm_deletion(archive_name)
            cmd_parts = [
                "borg",
                "delete",
                "-v",
                "--list",
                "--force",
                "--checkpoint-interval",
                "10",
                f"{self.repo_posix_path}::{archive_name}",
            ]

        rich_utils.run_and_log_sp_popen(
            cmd_parts=cmd_parts,
            status_message="[bold blue]Deleting archive[/]",
            success_message="Archive deleted successfully",
            error_message="Error deleting archive",
            spinner="toggle",
            use_stderr=True,
        )

    def sync_with_s3(self) -> None:
        """
        Sync the local Borg repository with an S3 bucket.

        This method will synchronize the contents of the Borg repository
        to the specified S3 bucket defined in the environment variable.
        """
        sync_source = self.repo_posix_path
        s3_destination_uri = f"s3://{environ['BORG_S3_BUCKET']}/{self.name}"
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
            spinner="pipe",
        )
        self.last_s3_sync = datetime.now(UTC)
