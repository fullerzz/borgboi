"""Class-based Borg client for BorgBoi.

This module provides a modern, class-based interface to the Borg backup tool.
It supports dependency injection for configuration and output handling,
making it easier to test and customize behavior.
"""

import io
import json
import os
import subprocess as sp
import threading
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from borgboi.clients.borg import (
    ArchivedFile,
    ArchiveInfo,
    DiffEntry,
    DiffResult,
    RepoArchive,
    RepoInfo,
)
from borgboi.config import BorgConfig, Config, get_config
from borgboi.core.errors import BorgError, BorgExitCode
from borgboi.core.logging import get_logger
from borgboi.core.models import BackupOptions, DiffOptions, RestoreOptions, RetentionPolicy
from borgboi.core.output import BaseOutputHandler, DefaultOutputHandler, SilentOutputHandler
from borgboi.core.telemetry import get_tracer, set_span_attributes
from borgboi.lib.utils import create_archive_name

logger = get_logger(__name__)
_STDERR_DRAIN_JOIN_TIMEOUT_SECONDS = 5.0
tracer = get_tracer(__name__)


@dataclass(frozen=True, slots=True)
class ExtractedFileContent:
    """Archived file bytes plus whether extraction stopped at a size cap."""

    payload: bytes
    truncated: bool


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
        output_handler: BaseOutputHandler | None = None,
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
        subcommand = cmd[1] if len(cmd) > 1 else cmd[0]
        with tracer.start_as_current_span("borg.command", kind=SpanKind.CLIENT) as span:
            set_span_attributes(
                span,
                {
                    "process.command.name": cmd[0],
                    "borgboi.borg.subcommand": subcommand,
                    "borgboi.capture_output": capture_output,
                },
            )
            env = self._build_env_with_passphrase(passphrase)
            result = sp.run(cmd, check=False, capture_output=capture_output, text=True, env=env)  # noqa: S603
            span.set_attribute("process.exit_code", result.returncode)
            self._handle_exit_code(result.returncode, cmd, result.stdout, result.stderr)
            return result

    def _run_command_bytes(
        self,
        cmd: list[str],
        passphrase: str | None = None,
    ) -> sp.CompletedProcess[bytes]:
        """Run a Borg command and capture stdout/stderr as bytes.

        Used for subcommands whose output is not guaranteed to be UTF-8 text
        (e.g. `borg extract --stdout` for arbitrary archived files).
        """
        subcommand = cmd[1] if len(cmd) > 1 else cmd[0]
        with tracer.start_as_current_span("borg.command", kind=SpanKind.CLIENT) as span:
            set_span_attributes(
                span,
                {
                    "process.command.name": cmd[0],
                    "borgboi.borg.subcommand": subcommand,
                    "borgboi.capture_output": True,
                    "borgboi.binary_output": True,
                },
            )
            env = self._build_env_with_passphrase(passphrase)
            result = sp.run(cmd, check=False, capture_output=True, env=env)  # noqa: S603
            span.set_attribute("process.exit_code", result.returncode)
            stdout_text = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            stderr_text = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            self._handle_exit_code(result.returncode, cmd, stdout_text, stderr_text)
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
        subcommand = cmd[1] if len(cmd) > 1 else cmd[0]
        span = tracer.start_span("borg.command.stream", kind=SpanKind.CLIENT)
        set_span_attributes(
            span,
            {
                "process.command.name": cmd[0],
                "borgboi.borg.subcommand": subcommand,
                "borgboi.stream_output": True,
            },
        )
        try:
            with trace.use_span(span, end_on_exit=False):
                env = self._build_env_with_passphrase(passphrase)
                proc = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.PIPE, env=env)  # noqa: S603

            # Borg progress messages use \r to overwrite the current terminal line.
            # TextIOWrapper's universal newlines translate \r, \n, and \r\n into \n,
            # so iterating yields clean line-oriented output regardless of style.
            text_stream = io.TextIOWrapper(proc.stderr, encoding="utf-8", errors="replace") if proc.stderr else None

            iteration_completed = False
            try:
                if text_stream is not None:
                    yield from text_stream
                iteration_completed = True
            finally:
                if text_stream is not None:
                    text_stream.close()
                elif proc.stderr:
                    proc.stderr.close()
                if proc.poll() is None:
                    proc.terminate()
                returncode = proc.wait()
                span.set_attribute("process.exit_code", returncode)
                if iteration_completed:
                    self._handle_exit_code(returncode, cmd)
        finally:
            span.end()

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
        logger.info("Initializing Borg repository via client", repo_path=repo_path, encryption=encryption)
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

        free_space = additional_free_space or self.config.additional_free_space
        if free_space:
            logger.debug("Setting additional free space", repo_path=repo_path, free_space=free_space)
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

        logger.info("Borg repository initialized via client", repo_path=repo_path)
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
        logger.debug("Getting repository info via client", repo_path=repo_path)
        cmd = [self.executable_path, "info", "--json", repo_path]
        result = self._run_command(cmd, passphrase=passphrase)
        repo_info = RepoInfo.model_validate_json(result.stdout)
        logger.debug(
            "Retrieved repository info via client",
            repo_path=repo_path,
            encryption_mode=repo_info.encryption.mode,
            archive_count=len(repo_info.archives),
        )
        return repo_info

    def set_storage_quota(self, repo_path: str, storage_quota: str, passphrase: str | None = None) -> None:
        """Update the storage quota for an existing repository.

        Args:
            repo_path: Path to the repository
            storage_quota: New storage quota for the repository (e.g., "200G", "1.5T")
            passphrase: Passphrase for encrypted repos

        Raises:
            BorgError: If the command fails
        """
        logger.info(
            "Updating Borg repository storage quota via client",
            repo_path=repo_path,
            storage_quota=storage_quota,
        )
        cmd = [
            self.executable_path,
            "config",
            "--log-json",
            "--progress",
            repo_path,
            "storage_quota",
            storage_quota,
        ]
        self._run_command(cmd, passphrase=passphrase)
        self.output.on_log("info", f"Updated storage quota for repository at {repo_path}")

    def get_additional_free_space(self, repo_path: str, passphrase: str | None = None) -> str | None:
        """Read the configured reserved free space for a repository.

        Args:
            repo_path: Path to the repository
            passphrase: Optional passphrase for encrypted repos

        Returns:
            Configured reserved free space, or None when the config value is empty

        Raises:
            BorgError: If the command fails
        """
        logger.debug("Reading Borg repository additional free space", repo_path=repo_path)
        cmd = [self.executable_path, "config", repo_path, "additional_free_space"]
        result = self._run_command(cmd, passphrase=passphrase)
        configured_free_space = result.stdout.strip()
        return configured_free_space or None

    def get_storage_quota(self, repo_path: str, passphrase: str | None = None) -> str | None:
        """Read the configured storage quota for a repository.

        Args:
            repo_path: Path to the repository
            passphrase: Optional passphrase for encrypted repos

        Returns:
            Configured storage quota, or None when the config value is unset

        Raises:
            BorgError: If the command fails
        """
        logger.debug("Reading Borg repository storage quota", repo_path=repo_path)
        cmd = [self.executable_path, "config", repo_path, "storage_quota"]
        result = self._run_command(cmd, passphrase=passphrase)
        configured_quota = result.stdout.strip()
        if configured_quota in {"", "0"}:
            return None
        return configured_quota

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
            archive_name = create_archive_name()
        logger.info(
            "Creating archive via client", repo_path=repo_path, archive_name=archive_name, backup_target=backup_target
        )

        opts = options or BackupOptions(compression=self.config.compression)
        cmd = [
            self.executable_path,
            "create",
            "--filter",
            "AME",
            "--show-rc",
            *opts.to_borg_args(),
        ]

        if exclude_file:
            logger.debug("Using exclusions file", exclude_file=exclude_file)
            cmd.extend(["--exclude-from", exclude_file])

        cmd.extend([f"{repo_path}::{archive_name}", backup_target])

        yield from self._run_streaming_command(cmd, passphrase=passphrase)
        logger.info("Archive creation completed via client", repo_path=repo_path, archive_name=archive_name)

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

    def extract_file_to_stdout(
        self,
        repo_path: str,
        archive_name: str,
        file_path: str,
        passphrase: str | None = None,
    ) -> bytes:
        """Extract a single archived file to stdout and return its raw bytes.

        Intended for TUI content-diff rendering; callers are responsible for
        enforcing size caps and detecting binary payloads before display.
        """
        logger.debug(
            "Extracting archived file to stdout via client",
            repo_path=repo_path,
            archive_name=archive_name,
            file_path=file_path,
        )
        cmd = [
            self.executable_path,
            "extract",
            "--stdout",
            f"{repo_path}::{archive_name}",
            file_path,
        ]
        result = self._run_command_bytes(cmd, passphrase=passphrase)
        return result.stdout or b""

    def extract_file_to_stdout_capped(
        self,
        repo_path: str,
        archive_name: str,
        file_path: str,
        *,
        max_bytes: int,
        passphrase: str | None = None,
    ) -> ExtractedFileContent:
        """Extract a single archived file, stopping once `max_bytes` is exceeded."""
        logger.debug(
            "Extracting archived file to stdout via client with size cap",
            repo_path=repo_path,
            archive_name=archive_name,
            file_path=file_path,
            max_bytes=max_bytes,
        )
        cmd = [
            self.executable_path,
            "extract",
            "--stdout",
            f"{repo_path}::{archive_name}",
            file_path,
        ]
        subcommand = cmd[1] if len(cmd) > 1 else cmd[0]
        with tracer.start_as_current_span("borg.command", kind=SpanKind.CLIENT) as span:
            set_span_attributes(
                span,
                {
                    "process.command.name": cmd[0],
                    "borgboi.borg.subcommand": subcommand,
                    "borgboi.capture_output": True,
                    "borgboi.binary_output": True,
                    "borgboi.max_bytes": max_bytes,
                },
            )
            env = self._build_env_with_passphrase(passphrase)
            proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, env=env)  # noqa: S603
            if proc.stdout is None:
                msg = "borg extract stdout pipe was not created"
                raise RuntimeError(msg)

            stderr_limit = 65536
            stderr_chunks: list[bytes] = []
            stderr_bytes_read = 0

            def drain_stderr() -> None:
                nonlocal stderr_bytes_read
                if proc.stderr is None:
                    return
                while chunk := proc.stderr.read(4096):
                    remaining = stderr_limit - stderr_bytes_read
                    if remaining > 0:
                        stderr_chunks.append(chunk[:remaining])
                        stderr_bytes_read += min(len(chunk), remaining)

            stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
            stderr_thread.start()

            limit = max_bytes + 1
            chunks: list[bytes] = []
            bytes_read = 0
            try:
                while bytes_read < limit:
                    chunk = proc.stdout.read(min(65536, limit - bytes_read))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    bytes_read += len(chunk)
            finally:
                proc.stdout.close()

            if bytes_read > max_bytes:
                proc.kill()
                returncode = proc.wait()
                stderr_thread.join(timeout=_STDERR_DRAIN_JOIN_TIMEOUT_SECONDS)
                stderr = b"".join(stderr_chunks)
                span.set_attribute("process.exit_code", returncode)
                if stderr:
                    span.set_attribute("borgboi.truncated.stderr", stderr.decode("utf-8", errors="replace"))
                return ExtractedFileContent(payload=b"".join(chunks)[:max_bytes], truncated=True)

            returncode = proc.wait()
            stderr_thread.join(timeout=_STDERR_DRAIN_JOIN_TIMEOUT_SECONDS)
            stderr = b"".join(stderr_chunks)
            span.set_attribute("process.exit_code", returncode)
            stdout = b"".join(chunks)
            stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
            self._handle_exit_code(returncode, cmd, stdout_text, stderr_text)
            return ExtractedFileContent(payload=stdout, truncated=False)

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
        logger.info("Deleting via client", repo_path=repo_path, archive_name=archive_name, dry_run=dry_run)

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
        logger.info("Delete completed via client", repo_path=repo_path, archive_name=archive_name, dry_run=dry_run)

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
        logger.info(
            "Pruning via client",
            repo_path=repo_path,
            keep_daily=policy.keep_daily,
            keep_weekly=policy.keep_weekly,
            keep_monthly=policy.keep_monthly,
            keep_yearly=policy.keep_yearly,
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
        logger.info("Prune completed via client", repo_path=repo_path)

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
        logger.info("Compacting via client", repo_path=repo_path)
        cmd = [
            self.executable_path,
            "compact",
            "--log-json",
            "--progress",
            repo_path,
        ]

        yield from self._run_streaming_command(cmd, passphrase=passphrase)
        logger.info("Compact completed via client", repo_path=repo_path)

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
        logger.debug("Listing archives via client", repo_path=repo_path)
        cmd = [self.executable_path, "list", "--json", repo_path]
        result = self._run_command(cmd, passphrase=passphrase)
        data = json.loads(result.stdout)
        archives = [RepoArchive.model_validate(arch) for arch in data.get("archives", [])]
        logger.debug("Listed archives via client", repo_path=repo_path, archive_count=len(archives))
        return archives

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
        logger.debug("Listing archive contents via client", repo_path=repo_path, archive_name=archive_name)
        cmd = [
            self.executable_path,
            "list",
            f"{repo_path}::{archive_name}",
            "--json-lines",
        ]
        result = self._run_command(cmd, passphrase=passphrase)
        contents = [ArchivedFile.model_validate_json(line) for line in result.stdout.splitlines() if line]
        logger.debug(
            "Listed archive contents via client",
            repo_path=repo_path,
            archive_name=archive_name,
            file_count=len(contents),
        )
        return contents

    def diff_archives(
        self,
        repo_path: str,
        archive1: str,
        archive2: str,
        options: DiffOptions | None = None,
        passphrase: str | None = None,
    ) -> DiffResult:
        """Compare two archives in a repository."""
        opts = options or DiffOptions()
        logger.info(
            "Diffing archives via client",
            repo_path=repo_path,
            archive1=archive1,
            archive2=archive2,
            content_only=opts.content_only,
            path_count=len(opts.paths),
        )
        cmd = [
            self.executable_path,
            "diff",
            *opts.to_borg_args(),
            "--json-lines",
            f"{repo_path}::{archive1}",
            archive2,
            *opts.paths,
        ]
        result = self._run_command(cmd, passphrase=passphrase)
        entries = [DiffEntry.model_validate_json(line) for line in result.stdout.splitlines() if line]
        logger.debug(
            "Diffed archives via client",
            repo_path=repo_path,
            archive1=archive1,
            archive2=archive2,
            entry_count=len(entries),
        )
        return DiffResult(archive1=archive1, archive2=archive2, entries=entries)

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
    handler: BaseOutputHandler = SilentOutputHandler() if silent else DefaultOutputHandler()
    return BorgClient(
        output_handler=handler,
        config=cfg.borg,
    )
