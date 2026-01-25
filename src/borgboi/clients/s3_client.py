"""Class-based S3 client for BorgBoi.

This module provides a modern, class-based interface for S3 operations,
replacing the procedural functions in s3.py. It supports dependency injection
for testing and different S3 backends.
"""

import json
import subprocess as sp
from abc import ABC, abstractmethod
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import override

from borgboi.config import AWSConfig, get_config
from borgboi.core.errors import StorageError
from borgboi.storage.models import S3RepoStats


class S3ClientInterface(ABC):
    """Abstract interface for S3 operations.

    This interface defines the contract for S3 clients, allowing for
    different implementations (real AWS, mock, etc.) to be swapped.
    """

    @abstractmethod
    def sync_to_bucket(self, local_path: str | Path, repo_name: str) -> Generator[str]:
        """Sync a local repository to S3.

        Args:
            local_path: Local path to the repository
            repo_name: Name of the repository (used as S3 prefix)

        Yields:
            Output lines from the sync operation

        Raises:
            StorageError: If the sync operation fails
        """
        ...

    @abstractmethod
    def sync_from_bucket(self, local_path: str | Path, repo_name: str, dry_run: bool = False) -> Generator[str]:
        """Sync a repository from S3 to local storage.

        Args:
            local_path: Local path to restore to
            repo_name: Name of the repository (used as S3 prefix)
            dry_run: If True, only show what would be synced

        Yields:
            Output lines from the sync operation

        Raises:
            StorageError: If the sync operation fails
        """
        ...

    @abstractmethod
    def delete_from_bucket(self, repo_name: str, dry_run: bool = False) -> Generator[str]:
        """Delete a repository from S3.

        Args:
            repo_name: Name of the repository to delete
            dry_run: If True, only show what would be deleted

        Yields:
            Output lines from the delete operation

        Raises:
            StorageError: If the delete operation fails
        """
        ...

    @abstractmethod
    def get_stats(self, repo_name: str) -> S3RepoStats:
        """Get S3 usage statistics for a repository.

        Args:
            repo_name: Name of the repository

        Returns:
            S3 statistics for the repository

        Raises:
            StorageError: If stats cannot be retrieved
        """
        ...

    @abstractmethod
    def exists(self, repo_name: str) -> bool:
        """Check if a repository exists in S3.

        Args:
            repo_name: Name of the repository

        Returns:
            True if the repository exists in S3
        """
        ...

    @abstractmethod
    def list_repos(self) -> list[str]:
        """List all repository prefixes in the S3 bucket.

        Returns:
            List of repository names in the bucket
        """
        ...


class S3Client(S3ClientInterface):
    """S3 client implementation using AWS CLI.

    This client uses the AWS CLI for S3 operations, which provides
    efficient sync operations with automatic multipart uploads and
    parallel transfers.

    Attributes:
        bucket: S3 bucket name
        storage_class: S3 storage class for uploads
        aws_cli_path: Path to AWS CLI executable
    """

    def __init__(
        self,
        bucket: str | None = None,
        storage_class: str = "INTELLIGENT_TIERING",
        aws_cli_path: str = "aws",
        config: AWSConfig | None = None,
    ) -> None:
        """Initialize the S3 client.

        Args:
            bucket: S3 bucket name (uses config if not provided)
            storage_class: S3 storage class for uploads
            aws_cli_path: Path to AWS CLI executable
            config: AWS configuration (uses global config if not provided)
        """
        self._config = config or get_config().aws
        self.bucket = bucket or self._config.s3_bucket
        self.storage_class = storage_class
        self.aws_cli_path = aws_cli_path

    def _s3_uri(self, repo_name: str) -> str:
        """Get the S3 URI for a repository.

        Args:
            repo_name: Repository name

        Returns:
            S3 URI for the repository
        """
        return f"s3://{self.bucket}/{repo_name}"

    def _run_streaming_command(self, cmd: list[str], error_msg: str = "S3 operation failed") -> Generator[str]:
        """Run a command and yield output lines.

        Args:
            cmd: Command to run
            error_msg: Error message prefix for failures

        Yields:
            Output lines from the command

        Raises:
            StorageError: If the command fails
        """
        proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)  # noqa: S603
        out_stream = proc.stdout

        if not out_stream:
            raise StorageError(f"{error_msg}: stdout is None")

        while out_stream.readable():
            line = out_stream.readline()
            if not line:
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
                break
            yield line.decode("utf-8").rstrip("\n")

        returncode = proc.wait()
        if returncode != 0:
            stderr = proc.stderr.read().decode("utf-8") if proc.stderr else ""
            raise StorageError(f"{error_msg} (exit code {returncode}): {stderr}", operation="s3_sync")

    @override
    def sync_to_bucket(self, local_path: str | Path, repo_name: str) -> Generator[str]:
        """Sync a local repository to S3.

        Args:
            local_path: Local path to the repository
            repo_name: Name of the repository

        Yields:
            Output lines from the sync operation
        """
        cmd = [
            self.aws_cli_path,
            "s3",
            "sync",
            str(local_path),
            self._s3_uri(repo_name),
            "--storage-class",
            self.storage_class,
        ]
        yield from self._run_streaming_command(cmd, f"Failed to sync {repo_name} to S3")

    @override
    def sync_from_bucket(self, local_path: str | Path, repo_name: str, dry_run: bool = False) -> Generator[str]:
        """Sync a repository from S3 to local storage.

        Args:
            local_path: Local path to restore to
            repo_name: Name of the repository
            dry_run: If True, only show what would be synced

        Yields:
            Output lines from the sync operation
        """
        cmd = [self.aws_cli_path, "s3"]
        if dry_run:
            cmd.append("--dryrun")
        cmd.extend(["sync", self._s3_uri(repo_name), str(local_path)])
        yield from self._run_streaming_command(cmd, f"Failed to restore {repo_name} from S3")

    @override
    def delete_from_bucket(self, repo_name: str, dry_run: bool = False) -> Generator[str]:
        """Delete a repository from S3.

        Args:
            repo_name: Name of the repository to delete
            dry_run: If True, only show what would be deleted

        Yields:
            Output lines from the delete operation
        """
        cmd = [self.aws_cli_path, "s3", "rm", self._s3_uri(repo_name), "--recursive"]
        if dry_run:
            cmd.append("--dryrun")
        yield from self._run_streaming_command(cmd, f"Failed to delete {repo_name} from S3")

    @override
    def get_stats(self, repo_name: str) -> S3RepoStats:
        """Get S3 usage statistics for a repository.

        Args:
            repo_name: Name of the repository

        Returns:
            S3 statistics for the repository
        """
        cmd = [
            self.aws_cli_path,
            "s3api",
            "list-objects-v2",
            "--bucket",
            self.bucket,
            "--prefix",
            f"{repo_name}/",
            "--query",
            "Contents[].{Size:Size,LastModified:LastModified}",
            "--output",
            "json",
        ]

        try:
            result = sp.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
            data = json.loads(result.stdout) if result.stdout.strip() else []

            total_size = sum(item.get("Size", 0) for item in data)
            object_count = len(data)

            # Find the most recent modification time
            last_modified = None
            for item in data:
                if item.get("LastModified"):
                    item_time = datetime.fromisoformat(item["LastModified"].replace("Z", "+00:00"))
                    if last_modified is None or item_time > last_modified:
                        last_modified = item_time

            return S3RepoStats(
                total_size_bytes=total_size,
                object_count=object_count,
                last_modified=last_modified,
                cached_at=datetime.now(),
            )
        except sp.CalledProcessError as e:
            raise StorageError(f"Failed to get stats for {repo_name}: {e.stderr}") from e
        except json.JSONDecodeError as e:
            raise StorageError(f"Failed to parse S3 stats response: {e}") from e

    @override
    def exists(self, repo_name: str) -> bool:
        """Check if a repository exists in S3.

        Args:
            repo_name: Name of the repository

        Returns:
            True if the repository exists in S3
        """
        cmd = [
            self.aws_cli_path,
            "s3",
            "ls",
            self._s3_uri(repo_name) + "/",
            "--summarize",
        ]

        try:
            result = sp.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
            return result.returncode == 0 and "Total Objects" in result.stdout
        except Exception:
            return False

    @override
    def list_repos(self) -> list[str]:
        """List all repository prefixes in the S3 bucket.

        Returns:
            List of repository names in the bucket
        """
        cmd = [
            self.aws_cli_path,
            "s3",
            "ls",
            f"s3://{self.bucket}/",
        ]

        try:
            result = sp.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
            repos = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    # S3 ls output format: "PRE repo_name/" for prefixes
                    parts = line.strip().split()
                    if parts and parts[0] == "PRE":
                        repo_name = parts[1].rstrip("/")
                        repos.append(repo_name)
            return repos
        except sp.CalledProcessError:
            return []


class MockS3Client(S3ClientInterface):
    """Mock S3 client for testing.

    This client simulates S3 operations in memory, allowing tests
    to run without AWS credentials or network access.

    Attributes:
        repos: Dictionary mapping repo names to their "content"
        stats: Dictionary mapping repo names to their stats
        sync_calls: List of sync_to_bucket calls for verification
        restore_calls: List of sync_from_bucket calls for verification
        delete_calls: List of delete_from_bucket calls for verification
    """

    def __init__(self) -> None:
        """Initialize the mock S3 client."""
        self.repos: dict[str, dict[str, bytes]] = {}
        self.stats: dict[str, S3RepoStats] = {}
        self.sync_calls: list[tuple[str, str]] = []
        self.restore_calls: list[tuple[str, str, bool]] = []
        self.delete_calls: list[tuple[str, bool]] = []

    def add_repo(self, repo_name: str, stats: S3RepoStats | None = None) -> None:
        """Add a mock repository.

        Args:
            repo_name: Name of the repository
            stats: Optional stats for the repository
        """
        self.repos[repo_name] = {}
        if stats:
            self.stats[repo_name] = stats
        else:
            self.stats[repo_name] = S3RepoStats(
                total_size_bytes=1024 * 1024 * 100,  # 100 MB
                object_count=10,
                last_modified=datetime.now(),
            )

    @override
    def sync_to_bucket(self, local_path: str | Path, repo_name: str) -> Generator[str]:
        """Mock sync to bucket.

        Args:
            local_path: Local path
            repo_name: Repository name

        Yields:
            Mock output lines
        """
        self.sync_calls.append((str(local_path), repo_name))
        self.repos[repo_name] = {}
        yield f"upload: {local_path} to s3://mock-bucket/{repo_name}/"

    @override
    def sync_from_bucket(self, local_path: str | Path, repo_name: str, dry_run: bool = False) -> Generator[str]:
        """Mock sync from bucket.

        Args:
            local_path: Local path
            repo_name: Repository name
            dry_run: Dry run flag

        Yields:
            Mock output lines
        """
        self.restore_calls.append((str(local_path), repo_name, dry_run))
        if repo_name not in self.repos:
            raise StorageError(f"Repository {repo_name} not found in S3")
        action = "(dryrun) download:" if dry_run else "download:"
        yield f"{action} s3://mock-bucket/{repo_name}/ to {local_path}"

    @override
    def delete_from_bucket(self, repo_name: str, dry_run: bool = False) -> Generator[str]:
        """Mock delete from bucket.

        Args:
            repo_name: Repository name
            dry_run: Dry run flag

        Yields:
            Mock output lines
        """
        self.delete_calls.append((repo_name, dry_run))
        if not dry_run and repo_name in self.repos:
            del self.repos[repo_name]
        action = "(dryrun) delete:" if dry_run else "delete:"
        yield f"{action} s3://mock-bucket/{repo_name}/"

    @override
    def get_stats(self, repo_name: str) -> S3RepoStats:
        """Get mock stats.

        Args:
            repo_name: Repository name

        Returns:
            Mock stats
        """
        if repo_name not in self.repos:
            raise StorageError(f"Repository {repo_name} not found in S3")
        return self.stats.get(repo_name, S3RepoStats())

    @override
    def exists(self, repo_name: str) -> bool:
        """Check if mock repo exists.

        Args:
            repo_name: Repository name

        Returns:
            True if repo exists in mock storage
        """
        return repo_name in self.repos

    @override
    def list_repos(self) -> list[str]:
        """List mock repos.

        Returns:
            List of mock repository names
        """
        return list(self.repos.keys())
