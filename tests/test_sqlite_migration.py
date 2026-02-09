"""Tests for SQLite auto-migration from legacy formats."""

import json
from pathlib import Path

import pytest

from borgboi.storage.db import RepositoryRow, S3StatsCacheRow, get_session_factory, init_db
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
    return borgboi_dir / "borgboi.db"


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

        db_path = borgboi_dir / "borgboi.db"
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

        db_path = borgboi_dir / "borgboi.db"
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
