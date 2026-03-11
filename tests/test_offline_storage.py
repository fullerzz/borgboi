from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from borgboi.core.errors import RepositoryNotFoundError, StorageError
from borgboi.models import BorgBoiRepo
from borgboi.storage.models import S3RepoStats
from borgboi.storage.offline import OfflineStorage


def _make_repo(name: str = "repo-one", path: str = "/repos/one", hostname: str = "host-a") -> BorgBoiRepo:
    return BorgBoiRepo(
        path=path,
        backup_target="/backup/source",
        name=name,
        hostname=hostname,
        os_platform="Darwin",
        metadata=None,
        passphrase_migrated=True,
    )


@pytest.fixture
def storage(tmp_path: Path) -> OfflineStorage:
    return OfflineStorage(base_dir=tmp_path / "data")


def test_save_get_list_and_exists_round_trip(storage: OfflineStorage) -> None:
    repo = _make_repo()
    storage.save(repo)

    assert storage.exists(repo.name) is True
    assert storage.get(repo.name).path == repo.path
    assert [saved_repo.name for saved_repo in storage.list_all()] == [repo.name]


def test_get_falls_back_to_metadata_file_when_index_missing(storage: OfflineStorage) -> None:
    repo = _make_repo()
    storage.save(repo)
    storage._index_file.unlink()

    result = storage.get(repo.name)

    assert result.name == repo.name


def test_get_by_path_scans_metadata_when_index_missing(storage: OfflineStorage) -> None:
    repo = _make_repo(hostname="host-b")
    storage.save(repo)
    storage._index_file.unlink()

    result = storage.get_by_path(repo.path, hostname="host-b")

    assert result.name == repo.name


def test_list_all_skips_invalid_metadata_files(storage: OfflineStorage) -> None:
    repo = _make_repo()
    storage.save(repo)
    (storage._metadata_dir / "broken.json").write_text("not-json", encoding="utf-8")

    repos = storage.list_all()

    assert [saved_repo.name for saved_repo in repos] == [repo.name]


def test_delete_invalidates_s3_cache(storage: OfflineStorage) -> None:
    repo = _make_repo()
    storage.save(repo)
    storage.update_s3_stats(repo.name, S3RepoStats(total_size_bytes=2048, object_count=3))

    storage.delete(repo.name)

    assert storage.get_s3_stats(repo.name) is None


def test_exclusions_round_trip_and_deduplicate(storage: OfflineStorage) -> None:
    storage.add_exclusion("repo-one", "*.tmp")
    storage.add_exclusion("repo-one", "  *.tmp  ")
    storage.add_exclusion("repo-one", ".cache/")

    assert storage.get_exclusions("repo-one") == ["*.tmp", ".cache/"]


@pytest.mark.parametrize("pattern", ["", "   ", "logs\narchive"])
def test_add_exclusion_rejects_blank_or_multiline(storage: OfflineStorage, pattern: str) -> None:
    with pytest.raises(ValueError, match="cannot"):
        storage.add_exclusion("repo-one", pattern)


def test_remove_exclusion_rejects_invalid_line_number(storage: OfflineStorage) -> None:
    storage.save_exclusions("repo-one", ["*.tmp"])

    with pytest.raises(ValueError, match="Invalid line number"):
        storage.remove_exclusion("repo-one", 2)


def test_load_index_raises_storage_error_for_corrupt_index(storage: OfflineStorage) -> None:
    storage._index_file.write_text("not-json", encoding="utf-8")

    with pytest.raises(StorageError, match="Failed to load repository index") as exc_info:
        storage._load_index()

    assert exc_info.value.operation == "load_index"


def test_corrupt_s3_cache_returns_empty_stats(storage: OfflineStorage) -> None:
    storage._s3_cache_file.write_text("not-json", encoding="utf-8")

    assert storage.get_s3_stats("repo-one") is None


def test_migrates_legacy_storage_on_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    home_dir = tmp_path / "home"
    legacy_dir = home_dir / ".borgboi_metadata"
    legacy_dir.mkdir(parents=True)
    repo = _make_repo(name="legacy-repo", path="/repos/legacy")
    (legacy_dir / "legacy-repo.json").write_text(repo.model_dump_json(indent=2), encoding="utf-8")
    (legacy_dir / "broken.json").write_text("not-json", encoding="utf-8")
    fake_config = SimpleNamespace(borgboi_dir=home_dir)

    monkeypatch.setattr("borgboi.storage.offline.get_config", lambda: fake_config)
    caplog.set_level("WARNING")

    storage = OfflineStorage(base_dir=tmp_path / "data")

    assert storage.get("legacy-repo").path == "/repos/legacy"
    assert "Failed to migrate legacy repository file 'broken.json'" in caplog.text
    assert "Failed to migrate 1 legacy repository files" in caplog.text


def test_get_by_path_raises_not_found_when_no_matching_repo(storage: OfflineStorage) -> None:
    with pytest.raises(RepositoryNotFoundError, match="not found"):
        storage.get_by_path("/missing")
