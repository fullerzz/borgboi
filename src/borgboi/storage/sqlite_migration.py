"""Auto-migration from legacy JSON formats to SQLite.

IMPORTANT: This module is imported during SQLiteStorage initialization before
borgboi.config.config is assigned. Therefore it MUST NOT import from borgboi.models,
borgboi.clients, or any module that imports borgboi.config at the top level.
Repository JSON files are parsed with raw json.loads() instead of Pydantic models
to avoid circular imports.
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from borgboi.storage.db import RepositoryRow, S3StatsCacheRow, get_session_factory, init_db

logger = logging.getLogger(__name__)


def auto_migrate_if_needed(db_path: Path) -> bool:
    """Check for legacy data and migrate to SQLite if needed.

    Called from SQLiteStorage.__init__ before accessing the database.

    Returns True if migration was performed, False otherwise.
    """
    if db_path.exists():
        return False

    borgboi_dir = db_path.parent

    # Check for any legacy data (repos and S3 cache only, not config)
    data_dir = borgboi_dir / "data"
    legacy_metadata_dir = borgboi_dir / ".borgboi_metadata"

    has_legacy = data_dir.exists() or legacy_metadata_dir.exists()

    if not has_legacy:
        # Fresh install: just create empty DB
        init_db(db_path)
        return False

    # Perform migration
    logger.info("Migrating legacy data to SQLite database at %s", db_path)
    engine = init_db(db_path)
    migrated_anything = _run_legacy_migrations(engine, data_dir, legacy_metadata_dir)

    return migrated_anything


def _run_legacy_migrations(engine: Engine, data_dir: Path, legacy_metadata_dir: Path) -> bool:
    """Execute all legacy format migrations and return True if anything was migrated."""
    migrated_anything = False

    if data_dir.exists():
        repos_dir = data_dir / "repositories"
        if repos_dir.exists():
            try:
                count = migrate_json_repositories(data_dir, engine)
                migrated_anything = migrated_anything or count > 0
                logger.info("Migrated %d repositories from JSON to SQLite", count)
            except Exception:
                logger.exception("Failed to migrate JSON repositories")

        s3_cache_path = data_dir / "s3_stats_cache.json"
        if s3_cache_path.exists():
            try:
                migrate_s3_cache(s3_cache_path, engine)
                migrated_anything = True
                logger.info("Migrated S3 stats cache to SQLite")
            except Exception:
                logger.exception("Failed to migrate S3 stats cache")

    if legacy_metadata_dir.exists():
        try:
            count = migrate_legacy_repositories(legacy_metadata_dir, engine)
            migrated_anything = migrated_anything or count > 0
            logger.info("Migrated %d repositories from legacy metadata to SQLite", count)
        except Exception:
            logger.exception("Failed to migrate legacy repositories")

    return migrated_anything


def migrate_json_repositories(data_dir: Path, engine: Engine) -> int:
    """Read JSON repository files and insert into the repositories table.

    Uses raw JSON parsing to avoid importing borgboi.models (circular import).
    """
    repos_dir = data_dir / "repositories"
    if not repos_dir.exists():
        return 0

    session_factory = get_session_factory(engine)
    count = 0

    for json_file in repos_dir.glob("*.json"):
        try:
            content = json_file.read_text()
            data = json.loads(content)
            _insert_repo_from_dict(session_factory, data)
            count += 1
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Skipping invalid repository file %s: %s", json_file.name, e)
        except Exception as e:
            logger.warning("Failed to migrate repository file %s: %s", json_file.name, e)

    return count


def migrate_legacy_repositories(legacy_dir: Path, engine: Engine) -> int:
    """Read legacy .borgboi_metadata/*.json files and insert into repositories table.

    Uses raw JSON parsing to avoid importing borgboi.models (circular import).
    """
    if not legacy_dir.exists():
        return 0

    session_factory = get_session_factory(engine)
    count = 0

    for json_file in legacy_dir.glob("*.json"):
        try:
            content = json_file.read_text()
            data = json.loads(content)
            _insert_repo_from_dict(session_factory, data)
            count += 1
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Skipping invalid legacy repository file %s: %s", json_file.name, e)
        except Exception as e:
            logger.warning("Failed to migrate legacy repository file %s: %s", json_file.name, e)

    return count


def migrate_s3_cache(cache_path: Path, engine: Engine) -> None:
    """Read S3 stats JSON cache and insert rows into s3_stats_cache table."""
    content = cache_path.read_text()
    data = json.loads(content)

    repos_data = data.get("repos", {})
    if not repos_data:
        return

    session_factory = get_session_factory(engine)
    with session_factory() as session:
        for repo_name, stats in repos_data.items():
            last_modified = None
            if stats.get("last_modified"):
                with contextlib.suppress(ValueError, TypeError):
                    last_modified = datetime.fromisoformat(stats["last_modified"])

            row = S3StatsCacheRow(
                repo_name=repo_name,
                total_size_bytes=stats.get("total_size_bytes", 0),
                object_count=stats.get("object_count", 0),
                last_modified=last_modified,
                cached_at=datetime.now(UTC),
            )
            session.add(row)
        session.commit()


def _insert_repo_from_dict(session_factory: Callable[[], Any], data: dict[str, Any]) -> None:
    """Insert a repository from a raw JSON dict into the repositories table.

    This avoids importing BorgBoiRepo (which triggers circular imports).
    Required keys: name, path, backup_target, hostname, os_platform.
    """
    name = str(data["name"])
    metadata_json: str | None = None
    metadata = data.get("metadata")
    if metadata is not None:
        metadata_json = json.dumps(metadata)

    last_backup = None
    if data.get("last_backup"):
        with contextlib.suppress(ValueError, TypeError):
            last_backup = datetime.fromisoformat(str(data["last_backup"]))

    row = RepositoryRow(
        name=name,
        path=str(data["path"]),
        backup_target=str(data["backup_target"]),
        hostname=str(data["hostname"]),
        os_platform=str(data["os_platform"]),
        last_backup=last_backup,
        metadata_json=metadata_json,
        passphrase=data.get("passphrase"),
        passphrase_file_path=data.get("passphrase_file_path"),
        passphrase_migrated=bool(data.get("passphrase_migrated", False)),
        updated_at=datetime.now(UTC),
    )

    with session_factory() as session:
        existing = session.query(RepositoryRow).filter_by(name=name).first()
        if existing is None:
            session.add(row)
            session.commit()
