from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from borgboi.models import BorgBoiRepo
from borgboi.storage import migration as migration_module


def _make_repo(name: str = "repo-one") -> BorgBoiRepo:
    return BorgBoiRepo(
        path=f"/repos/{name}",
        backup_target="/backup/source",
        name=name,
        hostname="host-a",
        os_platform="Darwin",
        metadata=None,
        passphrase_migrated=True,
    )


@dataclass
class FakeStorage:
    repos: list[BorgBoiRepo] = field(default_factory=list)
    existing: set[str] = field(default_factory=set)
    fail_on_save: set[str] = field(default_factory=set)
    list_error: Exception | None = None
    saved: list[str] = field(default_factory=list)

    def list_all(self) -> list[BorgBoiRepo]:
        if self.list_error is not None:
            raise self.list_error
        return self.repos

    def exists(self, name: str) -> bool:
        return name in self.existing

    def save(self, repo: BorgBoiRepo) -> None:
        if repo.name in self.fail_on_save:
            raise RuntimeError(f"save failed for {repo.name}")
        self.saved.append(repo.name)
        self.existing.add(repo.name)


def test_migration_result_properties() -> None:
    result = migration_module.MigrationResult(repos_migrated=2, repos_skipped=1)
    result.add_error("repo-three", "failed")

    assert result.total_processed == 4
    assert result.has_errors is True
    assert result.errors == [("repo-three", "failed")]


def test_migrate_offline_storage_returns_empty_when_source_missing(tmp_path: Path) -> None:
    result = migration_module.migrate_offline_storage(
        source_dir=tmp_path / "missing",
        target_storage=cast(Any, FakeStorage()),
    )

    assert result.repos_migrated == 0
    assert result.repos_skipped == 0
    assert result.errors == []


def test_migrate_offline_storage_dry_run_counts_without_saving(tmp_path: Path) -> None:
    repo = _make_repo()
    source_dir = tmp_path / "legacy"
    source_dir.mkdir()
    (source_dir / f"{repo.name}.json").write_text(repo.model_dump_json(indent=2), encoding="utf-8")
    target = FakeStorage()

    result = migration_module.migrate_offline_storage(
        source_dir=source_dir,
        target_storage=cast(Any, target),
        dry_run=True,
    )

    assert result.repos_migrated == 1
    assert target.saved == []


def test_migrate_offline_storage_skips_existing_repo(tmp_path: Path) -> None:
    repo = _make_repo()
    source_dir = tmp_path / "legacy"
    source_dir.mkdir()
    (source_dir / f"{repo.name}.json").write_text(repo.model_dump_json(indent=2), encoding="utf-8")
    target = FakeStorage(existing={repo.name})

    result = migration_module.migrate_offline_storage(source_dir=source_dir, target_storage=cast(Any, target))

    assert result.repos_skipped == 1
    assert result.repos_migrated == 0


def test_migrate_dynamodb_to_offline_records_list_failure() -> None:
    source = FakeStorage(list_error=RuntimeError("cannot list"))

    result = migration_module.migrate_dynamodb_to_offline(
        source_storage=cast(Any, source),
        target_storage=cast(Any, FakeStorage()),
    )

    assert result.errors == [("__all__", "Failed to list repositories: cannot list")]


def test_migrate_dynamodb_to_offline_records_per_repo_save_errors() -> None:
    repo_one = _make_repo("repo-one")
    repo_two = _make_repo("repo-two")
    source = FakeStorage(repos=[repo_one, repo_two])
    target = FakeStorage(fail_on_save={"repo-two"})

    result = migration_module.migrate_dynamodb_to_offline(
        source_storage=cast(Any, source),
        target_storage=cast(Any, target),
    )

    assert result.repos_migrated == 1
    assert result.errors == [("repo-two", "save failed for repo-two")]
    assert target.saved == ["repo-one"]


def test_migrate_offline_to_dynamodb_skips_existing_and_saves_new_repos() -> None:
    repo_one = _make_repo("repo-one")
    repo_two = _make_repo("repo-two")
    source = FakeStorage(repos=[repo_one, repo_two])
    target = FakeStorage(existing={"repo-one"})

    result = migration_module.migrate_offline_to_dynamodb(
        source_storage=cast(Any, source),
        target_storage=cast(Any, target),
    )

    assert result.repos_skipped == 1
    assert result.repos_migrated == 1
    assert target.saved == ["repo-two"]


def test_verify_migration_returns_missing_and_present_lists() -> None:
    repo_one = _make_repo("repo-one")
    repo_two = _make_repo("repo-two")
    source = FakeStorage(repos=[repo_one, repo_two])
    target = FakeStorage(existing={"repo-one"})

    missing, present = migration_module.verify_migration(
        source_storage=cast(Any, source),
        target_storage=cast(Any, target),
    )

    assert missing == ["repo-two"]
    assert present == ["repo-one"]


def test_verify_migration_returns_empty_lists_when_source_fails() -> None:
    source = FakeStorage(list_error=RuntimeError("cannot list"))

    missing, present = migration_module.verify_migration(
        source_storage=cast(Any, source),
        target_storage=cast(Any, FakeStorage()),
    )

    assert missing == []
    assert present == []
