"""Core Orchestrator for BorgBoi.

This module provides the main Orchestrator class that coordinates all
backup operations using dependency injection for testability.
"""

import shutil
import socket
from pathlib import Path
from platform import system

from borgboi.clients.borg import RepoArchive, RepoInfo
from borgboi.clients.borg_client import BorgClient, create_borg_client
from borgboi.clients.s3_client import S3ClientInterface
from borgboi.config import Config, get_config
from borgboi.core.errors import StorageError, ValidationError
from borgboi.core.models import BackupOptions, RestoreOptions, RetentionPolicy
from borgboi.core.output import DefaultOutputHandler, OutputHandler
from borgboi.lib.passphrase import (
    generate_secure_passphrase,
    migrate_repo_passphrase,
    resolve_passphrase,
    save_passphrase_to_file,
)
from borgboi.models import BorgBoiRepo
from borgboi.storage.base import RepositoryStorage


class Orchestrator:
    """Main orchestrator for BorgBoi operations.

    Coordinates backup, restore, and maintenance operations using
    dependency-injected clients and storage backends.

    Example:
        >>> orchestrator = Orchestrator()
        >>> repo = orchestrator.create_repo("/path/to/repo", "/home/user", "my-backups")
        >>> orchestrator.backup(repo)
    """

    def __init__(
        self,
        borg_client: BorgClient | None = None,
        storage: RepositoryStorage | None = None,
        s3_client: S3ClientInterface | None = None,
        config: Config | None = None,
        output_handler: OutputHandler | None = None,
    ) -> None:
        """Initialize Orchestrator with optional dependencies.

        Args:
            borg_client: Borg backup client (default: auto-created)
            storage: Repository storage backend (default: auto-created based on config)
            s3_client: S3 client for cloud sync (default: None)
            config: Configuration instance (default: get_config())
            output_handler: Handler for output messages (default: DefaultOutputHandler)
        """
        self.config = config or get_config()
        self.borg = borg_client or create_borg_client(config=self.config)
        self.storage = storage or self._create_default_storage()
        self.s3: S3ClientInterface | None = s3_client
        self.output = output_handler or DefaultOutputHandler()

    def _create_default_storage(self) -> RepositoryStorage:
        """Create the default storage backend based on configuration.

        Returns:
            RepositoryStorage instance (offline or DynamoDB)
        """
        if self.config.offline:
            from borgboi.storage.offline import OfflineStorage

            return OfflineStorage()
        else:
            from borgboi.storage.dynamodb import DynamoDBStorage

            return DynamoDBStorage(config=self.config)

    # Repository Workflows

    def create_repo(
        self,
        path: str,
        backup_target: str,
        name: str,
        passphrase: str | None = None,
        retention: RetentionPolicy | None = None,
    ) -> BorgBoiRepo:
        """Create a new Borg repository.

        Args:
            path: Path where the repository will be created
            backup_target: Path to the directory to back up
            name: Unique name for the repository
            passphrase: Optional passphrase (auto-generated if not provided)
            retention: Optional retention policy

        Returns:
            The created repository

        Raises:
            ValidationError: If parameters are invalid
            StorageError: If saving the repository fails
        """
        # Resolve or generate passphrase
        resolved_passphrase = resolve_passphrase(
            repo_name=name,
            cli_passphrase=passphrase,
            allow_env_fallback=True,
            env_var_name="BORG_NEW_PASSPHRASE",
        )

        if resolved_passphrase is None:
            resolved_passphrase = generate_secure_passphrase()
            self.output.on_log("warning", f"Generated passphrase for repo '{name}'")
            self.output.on_log("info", f"Passphrase: {resolved_passphrase}")
            self.output.on_log("warning", "SAVE THIS PASSPHRASE SECURELY!")

        # Save passphrase to file
        passphrase_file_path = save_passphrase_to_file(name, resolved_passphrase)
        self.output.on_log("info", f"Passphrase saved to: {passphrase_file_path}")

        # Create repo directory if needed
        repo_path = Path(path)
        if repo_path.is_file():
            raise ValidationError(f"Path {repo_path} is a file, not a directory", field="path")
        if not repo_path.exists():
            repo_path.mkdir(parents=True)

        # Determine if additional free space config should be applied
        # (skip for tmp/private directories)
        config_free_space = True
        if "/private/var/" in str(repo_path) or "tmp" in repo_path.parts:
            config_free_space = False

        # Initialize Borg repository
        self.borg.init(
            repo_path.as_posix(),
            passphrase=resolved_passphrase,
            additional_free_space=self.config.borg.additional_free_space if config_free_space else None,
        )

        # Get repository info
        repo_info = self.borg.info(repo_path.as_posix(), passphrase=resolved_passphrase)

        # Create repository model
        repo = BorgBoiRepo(
            path=repo_path.as_posix(),
            backup_target=backup_target,
            name=name,
            hostname=socket.gethostname(),
            os_platform=system(),
            metadata=repo_info,
            passphrase=None,  # Don't store in DB
            passphrase_file_path=passphrase_file_path.as_posix(),
            passphrase_migrated=True,
        )

        # Save to storage
        self.storage.save(repo)
        self.output.on_log("info", f"Created new Borg repo at {repo.path}")

        return repo

    def delete_repo(
        self,
        name: str | None = None,
        path: str | None = None,
        dry_run: bool = False,
        delete_from_s3: bool = False,
        passphrase: str | None = None,
    ) -> None:
        """Delete a repository.

        Args:
            name: Repository name
            path: Repository path
            dry_run: If True, only simulate deletion
            delete_from_s3: If True, also delete from S3
            passphrase: Optional passphrase override

        Raises:
            RepositoryNotFoundError: If repository not found
            ValidationError: If repository is not local
        """
        repo = self.get_repo(name=name, path=path)

        if not self._is_local(repo):
            raise ValidationError("Repository must be local to delete", field="repository")

        resolved_passphrase = self.resolve_passphrase(repo, passphrase)

        # Delete using Borg client
        for line in self.borg.delete(repo.path, dry_run=dry_run, passphrase=resolved_passphrase):
            self.output.on_stderr(line)

        if not dry_run:
            # Delete from storage
            self.storage.delete(repo.name)

            # Delete exclusions file
            self._delete_excludes_file(repo.name)

            # Delete from S3 if requested
            if delete_from_s3 and self.s3:
                # S3 deletion will be implemented in Phase 7
                pass

            self.output.on_log("info", f"Deleted repository {repo.name}")

    def get_repo(
        self,
        name: str | None = None,
        path: str | None = None,
        hostname: str | None = None,
    ) -> BorgBoiRepo:
        """Get a repository by name or path.

        Args:
            name: Repository name
            path: Repository path
            hostname: Optional hostname for path lookup

        Returns:
            The repository

        Raises:
            RepositoryNotFoundError: If not found
            ValueError: If neither name nor path provided
        """
        repo = self.storage.get_by_name_or_path(name=name, path=path, hostname=hostname)

        # Auto-migrate passphrase if needed
        repo = self._auto_migrate_passphrase(repo)

        return repo

    def list_repos(self) -> list[BorgBoiRepo]:
        """List all repositories.

        Returns:
            List of all repositories
        """
        return self.storage.list_all()

    # Backup Workflows

    def backup(
        self,
        repo: BorgBoiRepo | str,
        options: BackupOptions | None = None,
        passphrase: str | None = None,
    ) -> None:
        """Create a backup of the repository's target directory.

        Args:
            repo: Repository or repository name
            options: Backup options
            passphrase: Optional passphrase override
        """
        resolved_repo = self._resolve_repo(repo)
        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        # Check that excludes file exists
        excludes_path = self._get_excludes_path(resolved_repo.name)
        if not excludes_path.exists():
            raise ValidationError("Exclude list must be created before performing a backup", field="excludes")

        # Create archive
        for line in self.borg.create(
            resolved_repo.path,
            resolved_repo.backup_target,
            options=options,
            exclude_file=excludes_path.as_posix(),
            passphrase=resolved_passphrase,
        ):
            self.output.on_stderr(line)

        self.output.on_log("info", "Archive created successfully")

    def daily_backup(
        self,
        repo: BorgBoiRepo | str,
        passphrase: str | None = None,
        sync_to_s3: bool = True,
    ) -> None:
        """Perform a daily backup with prune and compact.

        Args:
            repo: Repository or repository name
            passphrase: Optional passphrase override
            sync_to_s3: Whether to sync to S3 after backup
        """
        resolved_repo = self._resolve_repo(repo)
        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        # Create archive
        self.output.on_log("info", "Creating new archive...")
        self.backup(resolved_repo, passphrase=resolved_passphrase)

        # Prune old archives
        self.output.on_log("info", "Pruning old backups...")
        self.prune(resolved_repo, passphrase=resolved_passphrase)

        # Compact repository
        self.output.on_log("info", "Compacting repository...")
        self.compact(resolved_repo, passphrase=resolved_passphrase)

        # Sync to S3 (if not offline and requested)
        if sync_to_s3 and not self.config.offline and self.s3:
            self.output.on_log("info", "Syncing to S3...")
            self.sync_to_s3(resolved_repo)

        # Refresh metadata
        repo_info = self.borg.info(resolved_repo.path, passphrase=resolved_passphrase)
        resolved_repo.metadata = repo_info
        self.storage.save(resolved_repo)

        self.output.on_log("info", "Daily backup completed successfully")

    def restore_archive(
        self,
        repo: BorgBoiRepo | str,
        archive_name: str,
        options: RestoreOptions | None = None,
        passphrase: str | None = None,
    ) -> None:
        """Restore an archive.

        Args:
            repo: Repository or repository name
            archive_name: Name of the archive to restore
            options: Restore options
            passphrase: Optional passphrase override
        """
        resolved_repo = self._resolve_repo(repo)
        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        for line in self.borg.extract(
            resolved_repo.path,
            archive_name,
            options=options,
            passphrase=resolved_passphrase,
        ):
            self.output.on_stderr(line)

        self.output.on_log("info", f"Archive {archive_name} restored successfully")

    def delete_archive(
        self,
        repo: BorgBoiRepo | str,
        archive_name: str,
        dry_run: bool = False,
        passphrase: str | None = None,
    ) -> None:
        """Delete an archive from a repository.

        Args:
            repo: Repository or repository name
            archive_name: Name of the archive to delete
            dry_run: If True, only simulate deletion
            passphrase: Optional passphrase override
        """
        resolved_repo = self._resolve_repo(repo)

        if not self._is_local(resolved_repo):
            raise ValidationError("Repository must be local to delete archives", field="repository")

        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        # Delete archive
        for line in self.borg.delete(
            resolved_repo.path,
            archive_name=archive_name,
            dry_run=dry_run,
            passphrase=resolved_passphrase,
        ):
            self.output.on_stderr(line)

        if not dry_run:
            # Compact after deletion to reclaim space
            self.compact(resolved_repo, passphrase=resolved_passphrase)

            # Refresh metadata
            repo_info = self.borg.info(resolved_repo.path, passphrase=resolved_passphrase)
            resolved_repo.metadata = repo_info
            self.storage.save(resolved_repo)

        self.output.on_log("info", f"Archive {archive_name} deleted successfully")

    # Maintenance Workflows

    def prune(
        self,
        repo: BorgBoiRepo | str,
        retention: RetentionPolicy | None = None,
        passphrase: str | None = None,
    ) -> None:
        """Prune old archives according to retention policy.

        Args:
            repo: Repository or repository name
            retention: Retention policy (defaults to config)
            passphrase: Optional passphrase override
        """
        resolved_repo = self._resolve_repo(repo)
        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        for line in self.borg.prune(
            resolved_repo.path,
            retention=retention,
            passphrase=resolved_passphrase,
        ):
            self.output.on_stderr(line)

        self.output.on_log("info", "Pruning completed")

    def compact(
        self,
        repo: BorgBoiRepo | str,
        passphrase: str | None = None,
    ) -> None:
        """Compact a repository to reclaim space.

        Args:
            repo: Repository or repository name
            passphrase: Optional passphrase override
        """
        resolved_repo = self._resolve_repo(repo)
        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        for line in self.borg.compact(
            resolved_repo.path,
            passphrase=resolved_passphrase,
        ):
            self.output.on_stderr(line)

        self.output.on_log("info", "Compacting completed")

    # S3 Workflows (stubs for Phase 7)

    def sync_to_s3(self, repo: BorgBoiRepo | str) -> None:
        """Sync a repository to S3.

        Args:
            repo: Repository or repository name
        """
        _ = self._resolve_repo(repo)  # Validate repo exists

        if self.s3 is None:
            self.output.on_log("warning", "S3 client not configured")
            return

        # Will be implemented in Phase 7
        self.output.on_log("info", "S3 sync not yet implemented in new orchestrator")

    def restore_from_s3(
        self,
        repo: BorgBoiRepo | str,
        dry_run: bool = False,
    ) -> None:
        """Restore a repository from S3.

        Args:
            repo: Repository or repository name
            dry_run: If True, only simulate restoration
        """
        _ = self._resolve_repo(repo)  # Validate repo exists
        _ = dry_run  # Will be used in Phase 7

        if self.s3 is None:
            self.output.on_log("warning", "S3 client not configured")
            return

        # Will be implemented in Phase 7
        self.output.on_log("info", "S3 restore not yet implemented in new orchestrator")

    # Archive Operations

    def list_archives(
        self,
        repo: BorgBoiRepo | str,
        passphrase: str | None = None,
    ) -> list[RepoArchive]:
        """List archives in a repository.

        Args:
            repo: Repository or repository name
            passphrase: Optional passphrase override

        Returns:
            List of archives
        """
        resolved_repo = self._resolve_repo(repo)
        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        return self.borg.list_archives(resolved_repo.path, passphrase=resolved_passphrase)

    def get_repo_info(
        self,
        repo: BorgBoiRepo | str,
        passphrase: str | None = None,
    ) -> RepoInfo:
        """Get detailed repository information.

        Args:
            repo: Repository or repository name
            passphrase: Optional passphrase override

        Returns:
            RepoInfo from Borg
        """
        resolved_repo = self._resolve_repo(repo)
        resolved_passphrase = self.resolve_passphrase(resolved_repo, passphrase)

        return self.borg.info(resolved_repo.path, passphrase=resolved_passphrase)

    # Exclusions Management

    def create_exclusions(
        self,
        repo: BorgBoiRepo | str,
        source_file: str,
    ) -> Path:
        """Create exclusions file for a repository.

        Args:
            repo: Repository or repository name
            source_file: Path to source file with exclusion patterns

        Returns:
            Path to the created exclusions file
        """
        resolved_repo = self._resolve_repo(repo)
        excludes_path = self._get_excludes_path(resolved_repo.name)

        if excludes_path.exists():
            raise ValidationError("Exclude list already created", field="excludes")

        # Ensure directory exists
        excludes_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy source file
        shutil.copy(source_file, excludes_path.as_posix())

        if not excludes_path.exists():
            raise StorageError("Excludes list not created", operation="create_exclusions")

        self.output.on_log("info", f"Exclude list created at {excludes_path}")
        return excludes_path

    def get_exclusions(self, repo: BorgBoiRepo | str) -> list[str]:
        """Get exclusion patterns for a repository.

        Args:
            repo: Repository or repository name

        Returns:
            List of exclusion patterns
        """
        resolved_repo = self._resolve_repo(repo)
        excludes_path = self._get_excludes_path(resolved_repo.name)

        if not excludes_path.exists():
            return []

        content = excludes_path.read_text()
        return [line.strip() for line in content.splitlines() if line.strip()]

    def add_exclusion(self, repo: BorgBoiRepo | str, pattern: str) -> None:
        """Add an exclusion pattern.

        Args:
            repo: Repository or repository name
            pattern: Exclusion pattern to add
        """
        resolved_repo = self._resolve_repo(repo)
        excludes_path = self._get_excludes_path(resolved_repo.name)

        if not excludes_path.exists():
            raise ValidationError("Exclude list not created", field="excludes")

        with excludes_path.open("a") as f:
            f.write(pattern + "\n")

        self.output.on_log("info", f"Added exclusion pattern: {pattern}")

    def remove_exclusion(self, repo: BorgBoiRepo | str, line_number: int) -> None:
        """Remove an exclusion pattern by line number.

        Args:
            repo: Repository or repository name
            line_number: 1-based line number to remove
        """
        resolved_repo = self._resolve_repo(repo)
        excludes_path = self._get_excludes_path(resolved_repo.name)

        if not excludes_path.exists():
            raise ValidationError("Exclude list not created", field="excludes")

        with excludes_path.open("r") as f:
            lines = f.readlines()

        if line_number < 1 or line_number > len(lines):
            raise ValidationError(f"Invalid line number: {line_number}", field="line_number")

        lines.pop(line_number - 1)

        with excludes_path.open("w") as f:
            f.writelines(lines)

        self.output.on_log("info", f"Removed exclusion at line {line_number}")

    # Passphrase Operations

    def resolve_passphrase(
        self,
        repo: BorgBoiRepo,
        cli_passphrase: str | None = None,
    ) -> str | None:
        """Resolve the passphrase for a repository.

        Args:
            repo: Repository
            cli_passphrase: Optional CLI-provided passphrase

        Returns:
            Resolved passphrase or None
        """
        return resolve_passphrase(
            repo_name=repo.name,
            cli_passphrase=cli_passphrase,
            db_passphrase=repo.passphrase,
            allow_env_fallback=True,
        )

    # Internal Helpers

    def _resolve_repo(self, repo: BorgBoiRepo | str) -> BorgBoiRepo:
        """Resolve a repository reference to a BorgBoiRepo object.

        Args:
            repo: Repository object or name string

        Returns:
            BorgBoiRepo instance
        """
        if isinstance(repo, str):
            return self.get_repo(name=repo)
        return repo

    def _is_local(self, repo: BorgBoiRepo) -> bool:
        """Check if a repository is on the local machine.

        Args:
            repo: Repository to check

        Returns:
            True if local
        """
        return repo.hostname == socket.gethostname()

    def _get_excludes_path(self, repo_name: str) -> Path:
        """Get the path to a repository's excludes file.

        Args:
            repo_name: Repository name

        Returns:
            Path to excludes file
        """
        return self.config.borgboi_dir / f"{repo_name}_{self.config.excludes_filename}"

    def _delete_excludes_file(self, repo_name: str) -> None:
        """Delete a repository's excludes file.

        Args:
            repo_name: Repository name
        """
        excludes_path = self._get_excludes_path(repo_name)
        if excludes_path.exists():
            excludes_path.unlink()
            self.output.on_log("info", f"Deleted excludes file for {repo_name}")

    def _auto_migrate_passphrase(self, repo: BorgBoiRepo) -> BorgBoiRepo:
        """Auto-migrate passphrase to file storage if needed.

        Args:
            repo: Repository to potentially migrate

        Returns:
            Updated repository (may be same if no migration needed)
        """
        if repo.passphrase_migrated or repo.passphrase is None:
            return repo

        self.output.on_log("warning", f"Auto-migrating passphrase for repo '{repo.name}' to file storage...")

        try:
            passphrase_file_path = migrate_repo_passphrase(repo.name, repo.passphrase)
            repo.passphrase_file_path = passphrase_file_path.as_posix()
            repo.passphrase_migrated = True

            self.storage.save(repo)
            self.output.on_log("info", f"Passphrase migrated to {passphrase_file_path}")
        except Exception as e:
            self.output.on_log("error", f"Failed to auto-migrate passphrase: {e}")
            self.output.on_log("warning", "Run 'bb migrate-passphrases' to migrate manually")

        return repo
