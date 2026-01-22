"""Offline storage implementation for BorgBoi.

This module provides local file-based storage for repository metadata,
used when running without AWS connectivity.
"""

import logging
import tempfile
import threading
from pathlib import Path

from pydantic import ValidationError

from borgboi.config import get_config
from borgboi.core.errors import RepositoryNotFoundError, StorageError
from borgboi.models import BorgBoiRepo
from borgboi.storage.base import RepositoryStorage
from borgboi.storage.models import RepositoryEntry, RepositoryIndex, S3RepoStats, S3StatsCache

logger = logging.getLogger(__name__)


class OfflineStorage(RepositoryStorage):
    """File-based storage for repository metadata.

    Stores repository metadata as individual JSON files with an index
    for fast lookups. Thread-safe for concurrent access.

    Attributes:
        base_dir: Base directory for all storage files
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize offline storage.

        Args:
            base_dir: Base directory for storage (default: ~/.borgboi/data)
        """
        config = get_config()
        self.base_dir = base_dir or config.borgboi_dir / "data"
        self._lock = threading.RLock()
        self._metadata_dir = self.base_dir / "repositories"
        self._index_file = self.base_dir / "repositories_index.json"
        self._exclusions_dir = self.base_dir / "exclusions"
        self._s3_cache_file = self.base_dir / "s3_stats_cache.json"

        # Ensure directories exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_dir.mkdir(parents=True, exist_ok=True)
        self._exclusions_dir.mkdir(parents=True, exist_ok=True)

        # Try to migrate from legacy storage if needed
        self._migrate_legacy_storage_if_needed()

    def _get_metadata_path(self, name: str) -> Path:
        """Get the path to a repository's metadata file.

        Args:
            name: Repository name

        Returns:
            Path to the metadata file
        """
        return self._metadata_dir / f"{name}.json"

    def _load_index(self) -> RepositoryIndex:
        """Load the repository index from disk.

        Returns:
            The repository index, or a new one if file doesn't exist
        """
        with self._lock:
            if self._index_file.exists():
                try:
                    content = self._index_file.read_text()
                    return RepositoryIndex.model_validate_json(content)
                except (OSError, ValueError, TypeError) as e:
                    raise StorageError(f"Failed to load repository index: {e}", operation="load_index", cause=e) from e
            return RepositoryIndex()

    def _save_index(self, index: RepositoryIndex) -> None:
        """Save the repository index to disk atomically.

        Uses a temporary file and atomic rename to prevent corruption
        if the write fails mid-operation.

        Args:
            index: The index to save
        """
        with self._lock:
            try:
                # Write to temp file first, then atomically rename
                fd, temp_path = tempfile.mkstemp(dir=self.base_dir, suffix=".tmp", prefix="index_")
                temp_file = Path(temp_path)
                try:
                    temp_file.write_text(index.model_dump_json(indent=2))
                    temp_file.replace(self._index_file)  # Atomic on POSIX
                finally:
                    # Clean up file descriptor
                    import os

                    os.close(fd)
                    # Remove temp file if it still exists (replace failed)
                    if temp_file.exists():
                        temp_file.unlink()
            except (OSError, ValueError, TypeError) as e:
                raise StorageError(f"Failed to save repository index: {e}", operation="save_index", cause=e) from e

    def _migrate_legacy_storage_if_needed(self) -> None:
        """Migrate from legacy per-repo storage if needed.

        Legacy storage kept individual JSON files in ~/.borgboi/.borgboi_metadata/
        This migrates them to the new indexed storage format.

        Logs warnings for any files that cannot be migrated so users are aware
        of potential issues with their repository metadata.
        """
        config = get_config()
        legacy_dir = config.borgboi_dir / ".borgboi_metadata"

        if not legacy_dir.exists():
            return

        with self._lock:
            index = self._load_index()
            migrated = 0
            skipped = 0
            errors: list[tuple[str, str]] = []

            for legacy_file in legacy_dir.glob("*.json"):
                try:
                    content = legacy_file.read_text()
                    repo = BorgBoiRepo.model_validate_json(content)

                    # Skip if already in index
                    if index.get(repo.name):
                        skipped += 1
                        continue

                    # Save to new location
                    new_path = self._get_metadata_path(repo.name)
                    new_path.write_text(repo.model_dump_json(indent=2))

                    # Add to index
                    entry = RepositoryEntry(
                        name=repo.name,
                        path=repo.path,
                        hostname=repo.hostname,
                        metadata_file=new_path.as_posix(),
                    )
                    index.add(entry)
                    migrated += 1
                except ValidationError as e:
                    error_msg = f"Invalid repository data: {e}"
                    errors.append((legacy_file.name, error_msg))
                    logger.warning(
                        "Failed to migrate legacy repository file '%s': %s",
                        legacy_file.name,
                        error_msg,
                    )
                except OSError as e:
                    error_msg = f"File I/O error: {e}"
                    errors.append((legacy_file.name, error_msg))
                    logger.warning(
                        "Failed to migrate legacy repository file '%s': %s",
                        legacy_file.name,
                        error_msg,
                    )

            if migrated > 0:
                self._save_index(index)
                logger.info(
                    "Migrated %d repositories from legacy storage (skipped %d already migrated)",
                    migrated,
                    skipped,
                )

            if errors:
                logger.warning(
                    "Failed to migrate %d legacy repository files. These repositories may need manual attention: %s",
                    len(errors),
                    ", ".join(f[0] for f in errors),
                )

    # RepositoryStorage implementation

    def get(self, name: str) -> BorgBoiRepo:
        """Retrieve a repository by name."""
        with self._lock:
            index = self._load_index()
            entry = index.get(name)

            if entry is None:
                # Fall back to direct file lookup for backwards compatibility
                path = self._get_metadata_path(name)
                if path.exists():
                    try:
                        content = path.read_text()
                        return BorgBoiRepo.model_validate_json(content)
                    except (OSError, ValueError, TypeError) as e:
                        raise StorageError(f"Failed to load repository {name}: {e}", operation="get", cause=e) from e
                raise RepositoryNotFoundError(f"Repository '{name}' not found", name=name)

            # Load from metadata file
            path = Path(entry.metadata_file) if entry.metadata_file else self._get_metadata_path(name)

            if not path.exists():
                raise RepositoryNotFoundError(f"Repository '{name}' metadata file not found", name=name)

            try:
                content = path.read_text()
                return BorgBoiRepo.model_validate_json(content)
            except (OSError, ValueError, TypeError) as e:
                raise StorageError(f"Failed to load repository {name}: {e}", operation="get", cause=e) from e

    def get_by_path(self, path: str, hostname: str | None = None) -> BorgBoiRepo:
        """Retrieve a repository by its path."""
        with self._lock:
            index = self._load_index()
            entry = index.find_by_path(path, hostname)

            if entry is None:
                # Fall back to scanning metadata files
                for metadata_file in self._metadata_dir.glob("*.json"):
                    try:
                        content = metadata_file.read_text()
                        repo = BorgBoiRepo.model_validate_json(content)
                        if repo.path == path and (hostname is None or repo.hostname == hostname):
                            return repo
                    except ValidationError:
                        # Skip files with invalid data structure
                        logger.debug("Skipping invalid metadata file: %s", metadata_file.name)
                        continue
                    except OSError as e:
                        # Log but continue - file may have been deleted or have permission issues
                        logger.warning("Could not read metadata file '%s': %s", metadata_file.name, e)
                        continue
                raise RepositoryNotFoundError(f"Repository at path '{path}' not found", path=path)

            return self.get(entry.name)

    def list_all(self) -> list[BorgBoiRepo]:
        """List all repositories in storage."""
        with self._lock:
            repos = []
            index = self._load_index()

            # Load from indexed entries
            for name in index.list_names():
                try:
                    repo = self.get(name)
                    repos.append(repo)
                except (RepositoryNotFoundError, StorageError):
                    # Skip entries that can't be loaded
                    continue

            # Also check for any unindexed files
            for metadata_file in self._metadata_dir.glob("*.json"):
                name = metadata_file.stem
                if name not in [r.name for r in repos]:
                    try:
                        content = metadata_file.read_text()
                        repo = BorgBoiRepo.model_validate_json(content)
                        repos.append(repo)
                    except (OSError, ValueError, TypeError):
                        continue

            return repos

    def save(self, repo: BorgBoiRepo) -> None:
        """Save or update repository metadata."""
        with self._lock:
            path = self._get_metadata_path(repo.name)

            try:
                path.write_text(repo.model_dump_json(indent=2))
            except (OSError, ValueError, TypeError) as e:
                raise StorageError(f"Failed to save repository {repo.name}: {e}", operation="save", cause=e) from e

            # Update index
            index = self._load_index()
            entry = RepositoryEntry(
                name=repo.name,
                path=repo.path,
                hostname=repo.hostname,
                metadata_file=path.as_posix(),
            )
            index.add(entry)
            self._save_index(index)

    def delete(self, name: str) -> None:
        """Delete a repository by name."""
        with self._lock:
            path = self._get_metadata_path(name)

            if not path.exists():
                # Check index
                index = self._load_index()
                if not index.get(name):
                    raise RepositoryNotFoundError(f"Repository '{name}' not found", name=name)

            try:
                if path.exists():
                    path.unlink()
            except OSError as e:
                raise StorageError(f"Failed to delete repository {name}: {e}", operation="delete", cause=e) from e

            # Update index
            index = self._load_index()
            index.remove(name)
            self._save_index(index)

            # Also invalidate S3 cache
            self.invalidate_s3_cache(name)

    def exists(self, name: str) -> bool:
        """Check if a repository exists."""
        with self._lock:
            # Check index first
            index = self._load_index()
            if index.get(name):
                return True

            # Fall back to file check
            return self._get_metadata_path(name).exists()

    # Exclusions management

    def get_exclusions_path(self, repo_name: str) -> Path:
        """Get path to exclusions file for a repository.

        Args:
            repo_name: Repository name

        Returns:
            Path to the exclusions file
        """
        return self._exclusions_dir / f"{repo_name}_excludes.txt"

    def get_exclusions(self, repo_name: str) -> list[str]:
        """Get exclusion patterns for a repository.

        Args:
            repo_name: Repository name

        Returns:
            List of exclusion patterns

        Raises:
            StorageError: If reading fails
        """
        path = self.get_exclusions_path(repo_name)
        if not path.exists():
            return []

        try:
            content = path.read_text()
            return [line.strip() for line in content.splitlines() if line.strip()]
        except OSError as e:
            raise StorageError(
                f"Failed to load exclusions for {repo_name}: {e}", operation="get_exclusions", cause=e
            ) from e

    def save_exclusions(self, repo_name: str, patterns: list[str]) -> None:
        """Save exclusion patterns for a repository.

        Args:
            repo_name: Repository name
            patterns: List of exclusion patterns

        Raises:
            StorageError: If saving fails
        """
        path = self.get_exclusions_path(repo_name)
        try:
            path.write_text("\n".join(patterns) + "\n")
        except OSError as e:
            raise StorageError(
                f"Failed to save exclusions for {repo_name}: {e}", operation="save_exclusions", cause=e
            ) from e

    def add_exclusion(self, repo_name: str, pattern: str) -> None:
        """Add an exclusion pattern for a repository.

        Args:
            repo_name: Repository name
            pattern: Exclusion pattern to add

        Raises:
            ValueError: If the pattern is empty or invalid
        """
        # Validate pattern
        stripped_pattern = pattern.strip()
        if not stripped_pattern:
            raise ValueError("Exclusion pattern cannot be empty")

        # Check for obviously invalid patterns (newlines would corrupt the file)
        if "\n" in stripped_pattern or "\r" in stripped_pattern:
            raise ValueError("Exclusion pattern cannot contain newline characters")

        patterns = self.get_exclusions(repo_name)
        if stripped_pattern not in patterns:
            patterns.append(stripped_pattern)
            self.save_exclusions(repo_name, patterns)

    def remove_exclusion(self, repo_name: str, line_number: int) -> None:
        """Remove an exclusion pattern by line number.

        Args:
            repo_name: Repository name
            line_number: 1-based line number to remove

        Raises:
            ValueError: If line number is invalid
        """
        patterns = self.get_exclusions(repo_name)
        if line_number < 1 or line_number > len(patterns):
            raise ValueError(f"Invalid line number {line_number}")
        patterns.pop(line_number - 1)
        self.save_exclusions(repo_name, patterns)

    # S3 cache operations

    def _load_s3_cache(self) -> S3StatsCache:
        """Load S3 stats cache from disk."""
        with self._lock:
            if self._s3_cache_file.exists():
                try:
                    content = self._s3_cache_file.read_text()
                    return S3StatsCache.model_validate_json(content)
                except (OSError, ValueError, TypeError):
                    return S3StatsCache()
            return S3StatsCache()

    def _save_s3_cache(self, cache: S3StatsCache) -> None:
        """Save S3 stats cache to disk atomically.

        Uses a temporary file and atomic rename to prevent corruption.
        Cache save failures are logged but not raised to avoid breaking operations.
        """
        with self._lock:
            try:
                # Write to temp file first, then atomically rename
                fd, temp_path = tempfile.mkstemp(dir=self.base_dir, suffix=".tmp", prefix="s3cache_")
                temp_file = Path(temp_path)
                try:
                    temp_file.write_text(cache.model_dump_json(indent=2))
                    temp_file.replace(self._s3_cache_file)  # Atomic on POSIX
                finally:
                    # Clean up file descriptor
                    import os

                    os.close(fd)
                    # Remove temp file if it still exists (replace failed)
                    if temp_file.exists():
                        temp_file.unlink()
            except (OSError, ValueError, TypeError) as e:
                # Log but don't raise - cache save failures shouldn't break operations
                logger.warning("Failed to save S3 stats cache: %s", e)

    def get_s3_stats(self, repo_name: str) -> S3RepoStats | None:
        """Get cached S3 stats for a repository.

        Args:
            repo_name: Repository name

        Returns:
            Cached S3 stats, or None if not cached
        """
        cache = self._load_s3_cache()
        return cache.get(repo_name)

    def update_s3_stats(self, repo_name: str, stats: S3RepoStats) -> None:
        """Update cached S3 stats for a repository.

        Args:
            repo_name: Repository name
            stats: S3 stats to cache
        """
        cache = self._load_s3_cache()
        cache.update(repo_name, stats)
        self._save_s3_cache(cache)

    def invalidate_s3_cache(self, repo_name: str) -> None:
        """Invalidate cached S3 stats for a repository.

        Args:
            repo_name: Repository name
        """
        cache = self._load_s3_cache()
        cache.invalidate(repo_name)
        self._save_s3_cache(cache)
