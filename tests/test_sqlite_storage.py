"""Tests for SQLiteStorage implementation."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from borgboi.core.errors import RepositoryNotFoundError
from borgboi.models import BorgBoiRepo
from borgboi.storage.db import init_db
from borgboi.storage.models import S3RepoStats
from borgboi.storage.sqlite import SQLiteStorage


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def storage(db_path: Path) -> Iterator[SQLiteStorage]:
    engine = init_db(db_path)
    s = SQLiteStorage(engine=engine)
    yield s
    s.close()


def _make_repo(name: str = "test-repo", path: str = "/repos/test", hostname: str = "localhost") -> BorgBoiRepo:
    return BorgBoiRepo(
        path=path,
        backup_target="/home/user",
        name=name,
        hostname=hostname,
        os_platform="Darwin",
        metadata=None,
    )


class TestSQLiteStorageCRUD:
    def test_save_and_get(self, storage: SQLiteStorage) -> None:
        repo = _make_repo()
        storage.save(repo)
        result = storage.get("test-repo")
        assert result.name == "test-repo"
        assert result.path == "/repos/test"
        assert result.backup_target == "/home/user"

    def test_get_not_found(self, storage: SQLiteStorage) -> None:
        with pytest.raises(RepositoryNotFoundError):
            storage.get("nonexistent")

    def test_save_updates_existing(self, storage: SQLiteStorage) -> None:
        repo = _make_repo()
        storage.save(repo)

        repo.backup_target = "/home/user2"
        storage.save(repo)

        result = storage.get("test-repo")
        assert result.backup_target == "/home/user2"

    def test_list_all_empty(self, storage: SQLiteStorage) -> None:
        assert storage.list_all() == []

    def test_list_all(self, storage: SQLiteStorage) -> None:
        storage.save(_make_repo("repo1", "/repos/1"))
        storage.save(_make_repo("repo2", "/repos/2"))
        repos = storage.list_all()
        assert len(repos) == 2
        names = {r.name for r in repos}
        assert names == {"repo1", "repo2"}

    def test_delete(self, storage: SQLiteStorage) -> None:
        storage.save(_make_repo())
        storage.delete("test-repo")
        assert not storage.exists("test-repo")

    def test_delete_not_found(self, storage: SQLiteStorage) -> None:
        with pytest.raises(RepositoryNotFoundError):
            storage.delete("nonexistent")

    def test_exists(self, storage: SQLiteStorage) -> None:
        assert not storage.exists("test-repo")
        storage.save(_make_repo())
        assert storage.exists("test-repo")

    def test_get_by_path(self, storage: SQLiteStorage) -> None:
        storage.save(_make_repo())
        result = storage.get_by_path("/repos/test")
        assert result.name == "test-repo"

    def test_get_by_path_with_hostname(self, storage: SQLiteStorage) -> None:
        storage.save(_make_repo("repo1", "/repos/test", "host1"))
        storage.save(_make_repo("repo2", "/repos/test", "host2"))
        result = storage.get_by_path("/repos/test", "host1")
        assert result.name == "repo1"

    def test_get_by_path_not_found(self, storage: SQLiteStorage) -> None:
        with pytest.raises(RepositoryNotFoundError):
            storage.get_by_path("/nonexistent")

    def test_get_by_path_ambiguous(self, storage: SQLiteStorage) -> None:
        storage.save(_make_repo("repo1", "/repos/test", "host1"))
        storage.save(_make_repo("repo2", "/repos/test", "host2"))
        with pytest.raises(ValueError, match="Multiple repositories"):
            storage.get_by_path("/repos/test")


class TestSQLiteStorageS3Cache:
    def test_get_s3_stats_empty(self, storage: SQLiteStorage) -> None:
        assert storage.get_s3_stats("test-repo") is None

    def test_update_and_get_s3_stats(self, storage: SQLiteStorage) -> None:
        stats = S3RepoStats(total_size_bytes=1024, object_count=10)
        storage.update_s3_stats("test-repo", stats)
        result = storage.get_s3_stats("test-repo")
        assert result is not None
        assert result.total_size_bytes == 1024
        assert result.object_count == 10

    def test_invalidate_s3_cache(self, storage: SQLiteStorage) -> None:
        stats = S3RepoStats(total_size_bytes=1024, object_count=10)
        storage.update_s3_stats("test-repo", stats)
        storage.invalidate_s3_cache("test-repo")
        assert storage.get_s3_stats("test-repo") is None

    def test_delete_repo_also_deletes_s3_cache(self, storage: SQLiteStorage) -> None:
        storage.save(_make_repo())
        stats = S3RepoStats(total_size_bytes=1024, object_count=10)
        storage.update_s3_stats("test-repo", stats)

        storage.delete("test-repo")
        assert storage.get_s3_stats("test-repo") is None
