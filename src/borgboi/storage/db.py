"""SQLAlchemy ORM models and database initialization for BorgBoi."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Engine,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from borgboi.core.logging import get_logger

if TYPE_CHECKING:
    from borgboi.config import Config

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


class RepositoryRow(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    backup_target: Mapped[str] = mapped_column(String(1024), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    os_platform: Mapped[str] = mapped_column(String(10), nullable=False)
    last_backup: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_keep_daily: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_keep_weekly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_keep_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_keep_yearly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_s3_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    passphrase: Mapped[str | None] = mapped_column(String(512), nullable=True)
    passphrase_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    passphrase_migrated: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    __table_args__ = (UniqueConstraint("path", "hostname", name="uq_repo_path_hostname"),)


class S3StatsCacheRow(Base):
    __tablename__ = "s3_stats_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    object_count: Mapped[int] = mapped_column(Integer, default=0)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class BackupStageTimingRow(Base):
    __tablename__ = "backup_stage_timings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stage_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class SchemaVersionRow(Base):
    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


def get_db_path(borgboi_dir: Path | None = None) -> Path:
    """Return the path to the borgboi SQLite database."""
    if borgboi_dir is not None:
        return borgboi_dir / ".database" / "borgboi.db"
    from borgboi.config import resolve_home_dir

    return resolve_home_dir() / ".borgboi" / ".database" / "borgboi.db"


def _set_sqlite_wal_mode(dbapi_connection: sqlite3.Connection, _connection_record: object) -> None:
    """Enable WAL mode for better concurrent read performance."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_engine(db_path: Path) -> Engine:
    """Create a SQLAlchemy engine for the given database path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False, poolclass=NullPool)
    event.listen(engine, "connect", _set_sqlite_wal_mode)
    return engine


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory for the given engine."""
    return sessionmaker(bind=engine)


def init_db(db_path: Path) -> Engine:
    """Create all tables and set initial schema version. Returns the engine."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)

    # Set schema version if not already set
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        existing = session.query(SchemaVersionRow).first()
        if existing is None:
            session.add(SchemaVersionRow(version=1))
            session.commit()

    return engine


def init_local_database(config: "Config") -> None:
    """Ensure the local metadata SQLite database exists and is migrated.

    Idempotent: safe to call multiple times. Logs at info level when a legacy
    layout will be migrated, debug otherwise. Disposes the engine before
    returning so callers receive a clean handle through their own storage.
    """
    from borgboi.storage.sqlite_migration import auto_migrate_if_needed

    db_path = get_db_path(config.borgboi_dir)
    if _should_log_sqlite_migration(db_path):
        logger.info("Migrating local metadata database", db_path=str(db_path))
    else:
        logger.debug("No SQLite migration needed", db_path=str(db_path))

    engine = auto_migrate_if_needed(db_path)
    engine.dispose()
    logger.debug("Local SQLite database initialized successfully")


def _should_log_sqlite_migration(db_path: Path) -> bool:
    """Return True when a legacy storage migration is expected."""
    if db_path.exists():
        return False

    borgboi_dir = db_path.parent.parent if db_path.parent.name == ".database" else db_path.parent

    legacy_db_path = borgboi_dir / "borgboi.db"
    legacy_data_path = borgboi_dir / "data"
    legacy_metadata_path = borgboi_dir / ".borgboi_metadata"
    return legacy_db_path.exists() or legacy_data_path.exists() or legacy_metadata_path.exists()
