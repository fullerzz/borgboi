"""SQLite storage implementation for BorgBoi using SQLAlchemy."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import override

from sqlalchemy import Engine

from borgboi.clients.borg import RepoInfo
from borgboi.core.errors import RepositoryNotFoundError, StorageError
from borgboi.models import BorgBoiRepo
from borgboi.storage.base import RepositoryStorage
from borgboi.storage.db import RepositoryRow, S3StatsCacheRow, get_db_path, get_session_factory, init_db
from borgboi.storage.models import S3RepoStats

logger = logging.getLogger(__name__)


class SQLiteStorage(RepositoryStorage):
    """SQLAlchemy-backed storage for repository metadata.

    Uses a SQLite database for persistence with proper session management.
    Thread-safe via SQLAlchemy's connection pooling.
    """

    def __init__(self, db_path: Path | None = None, engine: Engine | None = None) -> None:
        if engine is not None:
            self._engine = engine
        else:
            resolved_path = db_path or get_db_path()
            from borgboi.storage.sqlite_migration import auto_migrate_if_needed

            auto_migrate_if_needed(resolved_path)
            self._engine = init_db(resolved_path)
        self._session_factory = get_session_factory(self._engine)

    def close(self) -> None:
        """Dispose of the SQLAlchemy engine, releasing all connection resources."""
        self._engine.dispose()

    def _row_to_repo(self, row: RepositoryRow) -> BorgBoiRepo:
        """Convert a RepositoryRow to a BorgBoiRepo model."""
        metadata: RepoInfo | None = None
        if row.metadata_json:
            try:
                metadata = RepoInfo.model_validate_json(row.metadata_json)
            except Exception:
                logger.warning("Failed to parse metadata JSON for repo %s", row.name)

        return BorgBoiRepo(
            path=row.path,
            backup_target=row.backup_target,
            name=row.name,
            hostname=row.hostname,
            os_platform=row.os_platform,
            last_backup=row.last_backup,
            metadata=metadata,
            passphrase=row.passphrase,
            passphrase_file_path=row.passphrase_file_path,
            passphrase_migrated=row.passphrase_migrated,
        )

    def _repo_to_row_dict(self, repo: BorgBoiRepo) -> dict[str, object]:
        """Convert a BorgBoiRepo to a dict suitable for RepositoryRow."""
        metadata_json: str | None = None
        if repo.metadata is not None:
            metadata_json = repo.metadata.model_dump_json()

        return {
            "name": repo.name,
            "path": repo.path,
            "backup_target": repo.backup_target,
            "hostname": repo.hostname,
            "os_platform": repo.os_platform,
            "last_backup": repo.last_backup,
            "metadata_json": metadata_json,
            "passphrase": repo.passphrase,
            "passphrase_file_path": repo.passphrase_file_path,
            "passphrase_migrated": repo.passphrase_migrated,
            "updated_at": datetime.now(UTC),
        }

    @override
    def get(self, name: str) -> BorgBoiRepo:
        with self._session_factory() as session:
            row = session.query(RepositoryRow).filter_by(name=name).first()
            if row is None:
                raise RepositoryNotFoundError(f"Repository '{name}' not found", name=name)
            return self._row_to_repo(row)

    @override
    def get_by_path(self, path: str, hostname: str | None = None) -> BorgBoiRepo:
        with self._session_factory() as session:
            query = session.query(RepositoryRow).filter_by(path=path)
            if hostname is not None:
                query = query.filter_by(hostname=hostname)

            rows = query.all()
            if not rows:
                raise RepositoryNotFoundError(f"Repository at path '{path}' not found", path=path)

            if len(rows) > 1 and hostname is None:
                hostnames = [r.hostname for r in rows]
                raise ValueError(
                    f"Multiple repositories found at path '{path}' on different hosts: {hostnames}. "
                    "Please specify a hostname to disambiguate."
                )

            return self._row_to_repo(rows[0])

    @override
    def list_all(self) -> list[BorgBoiRepo]:
        with self._session_factory() as session:
            rows = session.query(RepositoryRow).all()
            return [self._row_to_repo(row) for row in rows]

    @override
    def save(self, repo: BorgBoiRepo) -> None:
        data = self._repo_to_row_dict(repo)
        with self._session_factory() as session:
            try:
                existing = session.query(RepositoryRow).filter_by(name=repo.name).first()
                if existing is not None:
                    for key, value in data.items():
                        if key != "name":
                            setattr(existing, key, value)
                else:
                    row = RepositoryRow(**data)
                    session.add(row)
                session.commit()
            except Exception as e:
                session.rollback()
                raise StorageError(f"Failed to save repository {repo.name}: {e}", operation="save", cause=e) from e

    @override
    def delete(self, name: str) -> None:
        with self._session_factory() as session:
            row = session.query(RepositoryRow).filter_by(name=name).first()
            if row is None:
                raise RepositoryNotFoundError(f"Repository '{name}' not found", name=name)
            try:
                session.delete(row)
                # Also delete S3 cache entry
                cache_row = session.query(S3StatsCacheRow).filter_by(repo_name=name).first()
                if cache_row is not None:
                    session.delete(cache_row)
                session.commit()
            except Exception as e:
                session.rollback()
                raise StorageError(f"Failed to delete repository {name}: {e}", operation="delete", cause=e) from e

    @override
    def exists(self, name: str) -> bool:
        with self._session_factory() as session:
            row = session.query(RepositoryRow).filter_by(name=name).first()
            return row is not None

    # S3 cache methods

    def get_s3_stats(self, repo_name: str) -> S3RepoStats | None:
        with self._session_factory() as session:
            row = session.query(S3StatsCacheRow).filter_by(repo_name=repo_name).first()
            if row is None:
                return None
            return S3RepoStats(
                total_size_bytes=row.total_size_bytes,
                object_count=row.object_count,
                last_modified=row.last_modified,
                cached_at=row.cached_at,
            )

    def update_s3_stats(self, repo_name: str, stats: S3RepoStats) -> None:
        with self._session_factory() as session:
            try:
                existing = session.query(S3StatsCacheRow).filter_by(repo_name=repo_name).first()
                if existing is not None:
                    existing.total_size_bytes = stats.total_size_bytes
                    existing.object_count = stats.object_count
                    existing.last_modified = stats.last_modified
                    existing.cached_at = datetime.now(UTC)
                else:
                    row = S3StatsCacheRow(
                        repo_name=repo_name,
                        total_size_bytes=stats.total_size_bytes,
                        object_count=stats.object_count,
                        last_modified=stats.last_modified,
                    )
                    session.add(row)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning("Failed to update S3 stats cache for %s: %s", repo_name, e)

    def invalidate_s3_cache(self, repo_name: str) -> None:
        with self._session_factory() as session:
            row = session.query(S3StatsCacheRow).filter_by(repo_name=repo_name).first()
            if row is not None:
                session.delete(row)
                session.commit()

    # Exclusions - delegate to file system (borg needs file paths)

    def get_exclusions_path(self, repo_name: str) -> Path:
        from borgboi.config import get_config

        config = get_config()
        return config.borgboi_dir / "data" / "exclusions" / f"{repo_name}_excludes.txt"

    def get_exclusions(self, repo_name: str) -> list[str]:
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
        path = self.get_exclusions_path(repo_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text("\n".join(patterns) + "\n")
        except OSError as e:
            raise StorageError(
                f"Failed to save exclusions for {repo_name}: {e}", operation="save_exclusions", cause=e
            ) from e

    def add_exclusion(self, repo_name: str, pattern: str) -> None:
        stripped_pattern = pattern.strip()
        if not stripped_pattern:
            raise ValueError("Exclusion pattern cannot be empty")
        if "\n" in stripped_pattern or "\r" in stripped_pattern:
            raise ValueError("Exclusion pattern cannot contain newline characters")

        patterns = self.get_exclusions(repo_name)
        if stripped_pattern not in patterns:
            patterns.append(stripped_pattern)
            self.save_exclusions(repo_name, patterns)

    def remove_exclusion(self, repo_name: str, line_number: int) -> None:
        patterns = self.get_exclusions(repo_name)
        if line_number < 1 or line_number > len(patterns):
            raise ValueError(f"Invalid line number {line_number}")
        patterns.pop(line_number - 1)
        self.save_exclusions(repo_name, patterns)
