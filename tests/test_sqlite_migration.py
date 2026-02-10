"""Tests for SQLite auto-migration from legacy formats."""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from borgboi.config import Config
from borgboi.core.orchestrator import Orchestrator
from borgboi.core.output import CollectingOutputHandler
from borgboi.storage.db import RepositoryRow, S3StatsCacheRow, get_db_path, get_session_factory, init_db
from borgboi.storage.sqlite_migration import (
    auto_migrate_if_needed,
    migrate_json_repositories,
    migrate_s3_cache,
)


@pytest.fixture
def borgboi_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".borgboi"
    d.mkdir()
    return d


@pytest.fixture
def db_path(borgboi_dir: Path) -> Path:
    db_dir = borgboi_dir / ".database"
    db_dir.mkdir()
    return db_dir / "borgboi.db"


def _make_repo_json(name: str = "test-repo", path: str = "/repos/test") -> str:
    """Create a repo JSON string without importing BorgBoiRepo (avoids circular imports in tests)."""
    return json.dumps(
        {
            "path": path,
            "backup_target": "/home/user",
            "name": name,
            "hostname": "localhost",
            "os_platform": "Darwin",
            "metadata": None,
            "passphrase": None,
            "passphrase_file_path": None,
            "passphrase_migrated": False,
        },
        indent=2,
    )


class TestMigrateJsonRepositories:
    def test_migrate_repos(self, borgboi_dir: Path) -> None:
        repos_dir = borgboi_dir / "data" / "repositories"
        repos_dir.mkdir(parents=True)
        (repos_dir / "repo1.json").write_text(_make_repo_json("repo1", "/repos/1"))
        (repos_dir / "repo2.json").write_text(_make_repo_json("repo2", "/repos/2"))

        db_path = borgboi_dir / ".database" / "borgboi.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = init_db(db_path)
        try:
            count = migrate_json_repositories(borgboi_dir / "data", engine)

            assert count == 2
            session_factory = get_session_factory(engine)
            with session_factory() as session:
                rows = session.query(RepositoryRow).all()
                names = {r.name for r in rows}
            assert names == {"repo1", "repo2"}
        finally:
            engine.dispose()


class TestMigrateS3Cache:
    def test_migrate_s3_cache(self, borgboi_dir: Path) -> None:
        cache_path = borgboi_dir / "data" / "s3_stats_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "version": 1,
            "repos": {
                "repo1": {"total_size_bytes": 1024, "object_count": 5},
                "repo2": {"total_size_bytes": 2048, "object_count": 10},
            },
        }
        cache_path.write_text(json.dumps(cache_data))

        db_path = borgboi_dir / ".database" / "borgboi.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = init_db(db_path)
        try:
            migrate_s3_cache(cache_path, engine)

            session_factory = get_session_factory(engine)
            with session_factory() as session:
                rows = session.query(S3StatsCacheRow).all()
                stats = {r.repo_name: r for r in rows}
            assert stats["repo1"].total_size_bytes == 1024
            assert stats["repo2"].object_count == 10
        finally:
            engine.dispose()


class TestAutoMigration:
    def test_fresh_install_creates_empty_db(self, borgboi_dir: Path, db_path: Path) -> None:
        """No legacy data, should create empty DB and return an engine."""
        engine = auto_migrate_if_needed(db_path)
        try:
            assert db_path.exists()
            assert hasattr(engine, "dispose")
        finally:
            engine.dispose()

    def test_skips_if_db_exists(self, borgboi_dir: Path, db_path: Path) -> None:
        engine = init_db(db_path)
        engine.dispose()
        engine = auto_migrate_if_needed(db_path)
        try:
            assert hasattr(engine, "dispose")
        finally:
            engine.dispose()

    def test_migrates_repositories(self, borgboi_dir: Path, db_path: Path) -> None:
        repos_dir = borgboi_dir / "data" / "repositories"
        repos_dir.mkdir(parents=True)
        (repos_dir / "repo1.json").write_text(_make_repo_json("repo1", "/repos/1"))

        engine = auto_migrate_if_needed(db_path)
        try:
            assert hasattr(engine, "dispose")

            from borgboi.storage.sqlite import SQLiteStorage

            storage = SQLiteStorage(engine=engine)
            repo = storage.get("repo1")
            assert repo.path == "/repos/1"
        finally:
            engine.dispose()

    def test_migrates_from_legacy_sqlite_path(self, borgboi_dir: Path, db_path: Path) -> None:
        legacy_db_path = borgboi_dir / "borgboi.db"
        legacy_engine = init_db(legacy_db_path)
        try:
            session_factory = get_session_factory(legacy_engine)
            with session_factory() as session:
                session.add(
                    RepositoryRow(
                        name="legacy-repo",
                        path="/repos/legacy",
                        backup_target="/home/user",
                        hostname="localhost",
                        os_platform="Darwin",
                    )
                )
                session.commit()
        finally:
            legacy_engine.dispose()

        engine = auto_migrate_if_needed(db_path)
        try:
            assert db_path.exists()
            assert not legacy_db_path.exists()

            from borgboi.storage.sqlite import SQLiteStorage

            storage = SQLiteStorage(engine=engine)
            repo = storage.get("legacy-repo")
            assert repo.path == "/repos/legacy"
        finally:
            engine.dispose()

    def test_custom_db_path_uses_parent_for_legacy_discovery(self, tmp_path: Path) -> None:
        db_path = tmp_path / "custom.db"
        repos_dir = tmp_path / "data" / "repositories"
        repos_dir.mkdir(parents=True)
        (repos_dir / "repo1.json").write_text(_make_repo_json("repo1", "/repos/1"))

        engine = auto_migrate_if_needed(db_path)
        try:
            from borgboi.storage.sqlite import SQLiteStorage

            storage = SQLiteStorage(engine=engine)
            repo = storage.get("repo1")
            assert repo.path == "/repos/1"
        finally:
            engine.dispose()


def test_online_orchestrator_bootstraps_local_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BORGBOI_OFFLINE", raising=False)

    migrated_db_path = get_db_path()
    borgboi_dir = migrated_db_path.parent.parent
    legacy_db_path = borgboi_dir / "borgboi.db"

    legacy_engine = init_db(legacy_db_path)
    try:
        session_factory = get_session_factory(legacy_engine)
        with session_factory() as session:
            session.add(
                RepositoryRow(
                    name="legacy-repo",
                    path="/repos/legacy",
                    backup_target="/home/user",
                    hostname="localhost",
                    os_platform="Darwin",
                )
            )
            session.commit()
    finally:
        legacy_engine.dispose()

    class DummyDynamoDBStorage:
        def __init__(self, config: Config | None = None, table_name: str | None = None) -> None:
            self.config = config
            self.table_name = table_name

    monkeypatch.setattr("borgboi.storage.dynamodb.DynamoDBStorage", DummyDynamoDBStorage)

    output_handler = CollectingOutputHandler()
    _ = Orchestrator(config=Config(offline=False), borg_client=cast(Any, object()), output_handler=output_handler)

    assert migrated_db_path.exists()
    assert not legacy_db_path.exists()
    assert any(
        message.startswith("Migrating local metadata database to") for _, message, _ in output_handler.log_messages
    )

    from borgboi.storage.sqlite import SQLiteStorage

    storage = SQLiteStorage(db_path=migrated_db_path)
    try:
        repo = storage.get("legacy-repo")
        assert repo.path == "/repos/legacy"
    finally:
        storage.close()
