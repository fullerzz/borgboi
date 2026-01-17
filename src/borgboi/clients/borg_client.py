"""Class-based Borg client for BorgBoi.

This module provides a modern, class-based interface to the Borg backup tool.
It supports dependency injection for configuration and output handling,
making it easier to test and customize behavior.
"""

import json
import os
import subprocess as sp
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

from borgboi.clients.borg import (
    ArchivedFile,
    ArchiveInfo,
    RepoArchive,
    RepoInfo,
)
from borgboi.config import BorgConfig, Config, get_config
from borgboi.core.errors import BorgError, BorgExitCode
from borgboi.core.models import BackupOptions, RestoreOptions, RetentionPolicy
from borgboi.core.output import DefaultOutputHandler, OutputHandler, SilentOutputHandler


class BorgClient:
    """Class-based Borg backup client.

    Provides a clean interface to Borg backup operations with support for
    dependency injection of configuration and output handling.

    Attributes:
        executable_path: Path to the Borg executable
        output: Output handler for command output
        config: Borg configuration
    """

    def __init__(
        self,
        executable_path: str | None = None,
        output_handler: OutputHandler | None = None,
        config: BorgConfig | None = None,
    ) -> None:
        """Initialize BorgClient.

        Args:
            executable_path: Path to borg executable (default: from config)
            output_handler: Handler for command output (default: DefaultOutputHandler)
            config: Borg configuration (default: from get_config())
        """
        full_config = get_config()
        self.config = config or full_config.borg
        self.executable_path = executable_path or self.config.executable_path
        self.output = output_handler or DefaultOutputHandler()

    def _build_env_with_passphrase(self, passphrase: str | None = None) -> dict[str, str] | None:
        """Build environment dict with BORG_PASSPHRASE if passphrase provided.

        Args:
            passphrase: Optional passphrase to set in environment

        Returns:
            Environment dict with BORG_PASSPHRASE set, or None if no passphrase
        """
        if passphrase is not None:
            env = os.environ.copy()
            env["BORG_PASSPHRASE"] = passphrase
            return env
        return None

    def _handle_exit_code(
        self,
        returncode: int,
        cmd: list[str],
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        """Handle Borg exit code, raising BorgError if necessary.

        Args:
            returncode: Exit code from Borg command
            cmd: Command that was executed
            stdout: Standard output
            stderr: Standard error

        Raises:
            BorgError: If the exit code indicates an error (not SUCCESS or WARNING)
        """
        if returncode == BorgExitCode.SUCCESS:
            return
        if returncode == BorgExitCode.WARNING:
            # Log warning but don't raise
            self.output.on_log("warning", f"Borg completed with warnings: {stderr}")
            return

        raise BorgError(
            message=f"Borg command failed with exit code {returncode}",
            exit_code=returncode,
            command=cmd,
            stdout=stdout,
            stderr=stderr,
        )

    def _run_command(
        self,
        cmd: list[str],
        passphrase: str | None = None,
        capture_output: bool = True,
    ) -> sp.CompletedProcess[str]:
        """Run a Borg command and return the result.

        Args:
            cmd: Command to execute
            passphrase: Optional passphrase for encrypted repos
            capture_output: Whether to capture stdout/stderr

        Returns:
            CompletedProcess with command results

        Raises:
            BorgError: If the command fails
        """
        env = self._build_env_with_passphrase(passphrase)
        result = sp.run(cmd, check=False, capture_output=capture_output, text=True, env=env)  # noqa: S603
        self._handle_exit_code(result.returncode, cmd, result.stdout, result.stderr)
        return result

    def _run_streaming_command(
        self,
        cmd: list[str],
        passphrase: str | None = None,
    ) -> Generator[str]:
        """Run a Borg command and yield output line by line.

        Args:
            cmd: Command to execute
            passphrase: Optional passphrase for encrypted repos

        Yields:
            Lines from stderr (where Borg sends its output)

        Raises:
            BorgError: If the command fails
        """
        env = self._build_env_with_passphrase(passphrase)
        proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603

        out_stream = proc.stderr
        while out_stream and out_stream.readable():
            line = out_stream.readline()
            if not line:
                break
            decoded = line.decode("utf-8")
            yield decoded

        # Clean up
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

        returncode = proc.wait()
        self._handle_exit_code(returncode, cmd)

    def _create_archive_name(self) -> str:
        """Create a unique archive name based on current timestamp.

        Returns:
            Archive name in format YYYY-MM-DD_HH:MM:SS
        """
        return datetime.now(UTC).strftime("%Y-%m-%d_%H:%M:%S")

    # Core Operations

    def init(
        self,
        repo_path: str,
        encryption: str = "repokey",
        passphrase: str | None = None,
        storage_quota: str | None = None,
        additional_free_space: str | None = None,
    ) -> None:
        """Initialize a new Borg repository.

        Args:
            repo_path: Path to the new repository
            encryption: Encryption mode (default: repokey)
            passphrase: Passphrase for encryption
            storage_quota: Storage quota for the repository
            additional_free_space: Reserved free space

        Raises:
            BorgError: If initialization fails
        """
        quota = storage_quota or self.config.storage_quota
        cmd = [
            self.executable_path,
            "init",
            "--log-json",
            "--progress",
            f"--encryption={encryption}",
            f"--storage-quota={quota}",
            repo_path,
        ]

        self._run_command(cmd, passphrase=passphrase)

        # Set additional_free_space if specified
        free_space = additional_free_space or self.config.additional_free_space
        if free_space:
            config_cmd = [
                self.executable_path,
                "config",
                "--log-json",
                "--progress",
                repo_path,
                "additional_free_space",
                free_space,
            ]
            self._run_command(config_cmd, passphrase=passphrase)

        self.output.on_log("info", f"Initialized repository at {repo_path}")

    def info(self, repo_path: str, passphrase: str | None = None) -> RepoInfo:
        """Get information about a repository.

        Args:
            repo_path: Path to the repository
            passphrase: Passphrase for encrypted repos

        Returns:
            RepoInfo with repository details

        Raises:
            BorgError: If the command fails
        """
        cmd = [self.executable_path, "info", "--json", repo_path]
        result = self._run_command(cmd, passphrase=passphrase)
        return RepoInfo.model_validate_json(result.stdout)

    def archive_info(
        self,
        repo_path: str,
        archive_name: str,
        passphrase: str | None = None,
    ) -> ArchiveInfo:
        """Get detailed information about a specific archive.

        Args:
            repo_path: Path to the repository
            archive_name: Name of the archive
            passphrase: Passphrase for encrypted repos

        Returns:
            ArchiveInfo with archive details

        Raises:
            BorgError: If the command fails
        """
        cmd = [self.executable_path, "info", "--json", f"{repo_path}::{archive_name}"]
        result = self._run_command(cmd, passphrase=passphrase)
        return ArchiveInfo.model_validate_json(result.stdout)

    # Streaming Operations

    def create(
        self,
        repo_path: str,
        backup_target: str,
        archive_name: str | None = None,
        options: BackupOptions | None = None,
        exclude_file: str | None = None,
        passphrase: str | None = None,
    ) -> Generator[str]:
        """Create a new archive.

        Args:
            repo_path: Path to the repository
            backup_target: Path to back up
            archive_name: Optional archive name (default: auto-generated)
            options: Backup options
            exclude_file: Path to exclude patterns file
            passphrase: Passphrase for encrypted repos

        Yields:
            Output lines from Borg

        Raises:
            BorgError: If the command fails
        """
        if archive_name is None:
            archive_name = self._create_archive_name()

        opts = options or BackupOptions()
        cmd = [
            self.executable_path,
            "create",
            "--filter",
            "AME",
            "--show-rc",
            *opts.to_borg_args(),
        ]

        if exclude_file:
            cmd.extend(["--exclude-from", exclude_file])

        cmd.extend([f"{repo_path}::{archive_name}", backup_target])

        yield from self._run_streaming_command(cmd, passphrase=passphrase)

    def extract(
        self,
        repo_path: str,
        archive_name: str,
        options: RestoreOptions | None = None,
        passphrase: str | None = None,
    ) -> Generator[str]:
        """Extract an archive.

        Args:
            repo_path: Path to the repository
            archive_name: Name of the archive to extract
            options: Restore options
            passphrase: Passphrase for encrypted repos

        Yields:
            Output lines from Borg

        Raises:
            BorgError: If the command fails
        """
        opts = options or RestoreOptions()
        cmd = [
            self.executable_path,
            "extract",
            "--log-json",
            *opts.to_borg_args(),
            f"{repo_path}::{archive_name}",
        ]

        yield from self._run_streaming_command(cmd, passphrase=passphrase)

    def delete(
        self,
        repo_path: str,
        archive_name: str | None = None,
        dry_run: bool = False,
        passphrase: str | None = None,
    ) -> Generator[str]:
        """Delete a repository or archive.

        Args:
            repo_path: Path to the repository
            archive_name: Optional archive name (if None, deletes entire repo)
            dry_run: If True, only simulate deletion
            passphrase: Passphrase for encrypted repos

        Yields:
            Output lines from Borg

        Raises:
            BorgError: If the command fails
        """
        target = f"{repo_path}::{archive_name}" if archive_name else repo_path

        cmd = [
            self.executable_path,
            "delete",
            "--log-json",
            "--progress",
            "--list",
            "--force",
            "--checkpoint-interval",
            str(self.config.checkpoint_interval // 90),
        ]

        if dry_run:
            cmd.append("--dry-run")

        cmd.append(target)

        yield from self._run_streaming_command(cmd, passphrase=passphrase)

    def prune(
        self,
        repo_path: str,
        retention: RetentionPolicy | None = None,
        passphrase: str | None = None,
    ) -> Generator[str]:
        """Prune old archives according to retention policy.

        Args:
            repo_path: Path to the repository
            retention: Retention policy (default: from config)
            passphrase: Passphrase for encrypted repos

        Yields:
            Output lines from Borg

        Raises:
            BorgError: If the command fails
        """
        policy = retention or RetentionPolicy(
            keep_daily=self.config.retention.keep_daily,
            keep_weekly=self.config.retention.keep_weekly,
            keep_monthly=self.config.retention.keep_monthly,
            keep_yearly=self.config.retention.keep_yearly,
        )

        cmd = [
            self.executable_path,
            "prune",
            "--log-json",
            "--progress",
            "--list",
            *policy.to_borg_args(),
            repo_path,
        ]

        yield from self._run_streaming_command(cmd, passphrase=passphrase)

    def compact(
        self,
        repo_path: str,
        passphrase: str | None = None,
    ) -> Generator[str]:
        """Compact repository to reclaim space.

        Args:
            repo_path: Path to the repository
            passphrase: Passphrase for encrypted repos

        Yields:
            Output lines from Borg

        Raises:
            BorgError: If the command fails
        """
        cmd = [
            self.executable_path,
            "compact",
            "--log-json",
            "--progress",
            repo_path,
        ]

        yield from self._run_streaming_command(cmd, passphrase=passphrase)

    # Listing Operations

    def list_archives(
        self,
        repo_path: str,
        passphrase: str | None = None,
    ) -> list[RepoArchive]:
        """List archives in a repository.

        Args:
            repo_path: Path to the repository
            passphrase: Passphrase for encrypted repos

        Returns:
            List of archives in the repository

        Raises:
            BorgError: If the command fails
        """
        cmd = [self.executable_path, "list", "--json", repo_path]
        result = self._run_command(cmd, passphrase=passphrase)
        data = json.loads(result.stdout)
        return [RepoArchive.model_validate(arch) for arch in data.get("archives", [])]

    def list_archive_contents(
        self,
        repo_path: str,
        archive_name: str,
        passphrase: str | None = None,
    ) -> list[ArchivedFile]:
        """List contents of an archive.

        Args:
            repo_path: Path to the repository
            archive_name: Name of the archive
            passphrase: Passphrase for encrypted repos

        Returns:
            List of files in the archive

        Raises:
            BorgError: If the command fails
        """
        cmd = [
            self.executable_path,
            "list",
            f"{repo_path}::{archive_name}",
            "--json-lines",
        ]
        result = self._run_command(cmd, passphrase=passphrase)
        return [ArchivedFile.model_validate_json(line) for line in result.stdout.splitlines() if line]

    # Key Operations

    def export_key(
        self,
        repo_path: str,
        output_path: Path,
        paper: bool = True,
        passphrase: str | None = None,
    ) -> Path:
        """Export repository key to a file.

        Args:
            repo_path: Path to the repository
            output_path: Path to write the key to
            paper: If True, export in paper backup format
            passphrase: Passphrase for encrypted repos

        Returns:
            Path to the exported key file

        Raises:
            BorgError: If the command fails
        """
        cmd = [self.executable_path, "key", "export"]
        if paper:
            cmd.append("--paper")
        cmd.extend([repo_path, output_path.as_posix()])

        self._run_command(cmd, passphrase=passphrase)
        return output_path


def create_borg_client(
    silent: bool = False,
    config: Config | None = None,
) -> BorgClient:
    """Factory function to create a BorgClient with appropriate configuration.

    Args:
        silent: If True, use SilentOutputHandler
        config: Optional configuration (default: get_config())

    Returns:
        Configured BorgClient instance
    """
    cfg = config or get_config()
    handler: OutputHandler = SilentOutputHandler() if silent else DefaultOutputHandler()
    return BorgClient(
        output_handler=handler,
        config=cfg.borg,
    )
