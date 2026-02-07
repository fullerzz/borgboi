"""Tests for SQLite auto-migration from legacy formats."""

import json
from pathlib import Path

import pytest
import yaml

from borgboi.storage.db import ConfigRow, RepositoryRow, S3StatsCacheRow, get_session_factory, init_db
from borgboi.storage.sqlite_migration import (
    auto_migrate_if_needed,
    migrate_json_repositories,
    migrate_s3_cache,
    migrate_yaml_config,
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


class TestMigrateYamlConfig:
    def test_basic_yaml_migration(self, borgboi_dir: Path) -> None:
        config_yaml = borgboi_dir / "config.yaml"
        config_yaml.write_text(
            yaml.safe_dump(
                {
                    "offline": True,
                    "aws": {"s3_bucket": "my-bucket", "region": "us-east-1"},
                    "borg": {"compression": "lz4", "retention": {"keep_daily": 14}},
                }
            )
        )

        db_path = borgboi_dir / "borgboi.db"
        engine = init_db(db_path)
        migrate_yaml_config(config_yaml, engine)

        session_factory = get_session_factory(engine)
        with session_factory() as session:
            rows = session.query(ConfigRow).all()
            row_map = {(r.section, r.key): json.loads(r.value) for r in rows}

        assert row_map[("top", "offline")] is True
        assert row_map[("aws", "s3_bucket")] == "my-bucket"
        assert row_map[("aws", "region")] == "us-east-1"
        assert row_map[("borg", "compression")] == "lz4"
        assert row_map[("borg.retention", "keep_daily")] == 14


class TestMigrateJsonRepositories:
    def test_migrate_repos(self, borgboi_dir: Path) -> None:
        repos_dir = borgboi_dir / "data" / "repositories"
        repos_dir.mkdir(parents=True)
        (repos_dir / "repo1.json").write_text(_make_repo_json("repo1", "/repos/1"))
        (repos_dir / "repo2.json").write_text(_make_repo_json("repo2", "/repos/2"))

        db_path = borgboi_dir / "borgboi.db"
        engine = init_db(db_path)
        count = migrate_json_repositories(borgboi_dir / "data", engine)

        assert count == 2
        session_factory = get_session_factory(engine)
        with session_factory() as session:
            rows = session.query(RepositoryRow).all()
            names = {r.name for r in rows}
        assert names == {"repo1", "repo2"}


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
        migrate_s3_cache(cache_path, engine)

        session_factory = get_session_factory(engine)
        with session_factory() as session:
            rows = session.query(S3StatsCacheRow).all()
            stats = {r.repo_name: r for r in rows}
        assert stats["repo1"].total_size_bytes == 1024
        assert stats["repo2"].object_count == 10


class TestAutoMigration:
    def test_fresh_install_creates_empty_db(self, borgboi_dir: Path, db_path: Path) -> None:
        """No legacy data, should create empty DB."""
        result = auto_migrate_if_needed(db_path)
        assert result is False
        assert db_path.exists()

    def test_skips_if_db_exists(self, borgboi_dir: Path, db_path: Path) -> None:
        init_db(db_path)
        result = auto_migrate_if_needed(db_path)
        assert result is False

    def test_migrates_yaml_and_renames(self, borgboi_dir: Path, db_path: Path) -> None:
        config_yaml = borgboi_dir / "config.yaml"
        config_yaml.write_text(yaml.safe_dump({"offline": True}))

        result = auto_migrate_if_needed(db_path)
        assert result is True
        assert db_path.exists()
        assert not config_yaml.exists()
        assert (borgboi_dir / "config.yaml.bak").exists()

    def test_migrates_repositories(self, borgboi_dir: Path, db_path: Path) -> None:
        repos_dir = borgboi_dir / "data" / "repositories"
        repos_dir.mkdir(parents=True)
        (repos_dir / "repo1.json").write_text(_make_repo_json("repo1", "/repos/1"))

        result = auto_migrate_if_needed(db_path)
        assert result is True

        from borgboi.storage.sqlite import SQLiteStorage

        storage = SQLiteStorage(db_path=db_path)
        repo = storage.get("repo1")
        assert repo.path == "/repos/1"
