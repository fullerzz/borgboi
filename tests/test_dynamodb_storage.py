from __future__ import annotations

from types import SimpleNamespace

import pytest

from borgboi.config import Config
from borgboi.core.errors import RepositoryNotFoundError, StorageError
from borgboi.models import BorgBoiRepo
from borgboi.storage.dynamodb import DynamoDBStorage


def _make_repo(name: str = "repo-one", path: str = "/repos/one", hostname: str = "remote-host") -> BorgBoiRepo:
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
def storage(create_dynamodb_table: None) -> DynamoDBStorage:
    del create_dynamodb_table
    return DynamoDBStorage(config=Config())


def test_save_and_get_round_trip(storage: DynamoDBStorage) -> None:
    repo = _make_repo()

    storage.save(repo)
    result = storage.get(repo.name)

    assert result.name == repo.name
    assert result.path == repo.path
    assert result.backup_target == repo.backup_target


def test_get_by_path_uses_explicit_hostname(storage: DynamoDBStorage) -> None:
    repo = _make_repo(hostname="host-a")
    storage.save(repo)

    result = storage.get_by_path(repo.path, hostname="host-a")

    assert result.name == repo.name
    assert result.hostname == "host-a"


def test_get_by_path_defaults_to_current_hostname(
    storage: DynamoDBStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_repo(hostname="storage-host")
    storage.save(repo)
    monkeypatch.setattr("borgboi.storage.dynamodb.socket.gethostname", lambda: "storage-host")
    monkeypatch.setattr("borgboi.clients.dynamodb.borg.info", lambda repo_path, passphrase=None: None)

    result = storage.get_by_path(repo.path)

    assert result.name == repo.name
    assert result.hostname == repo.hostname


def test_get_raises_not_found_for_missing_repo(storage: DynamoDBStorage) -> None:
    with pytest.raises(RepositoryNotFoundError, match="not found"):
        storage.get("missing")


def test_get_wraps_invalid_table_item_as_storage_error(storage: DynamoDBStorage) -> None:
    storage._table.put_item(Item={"repo_path": "/broken", "hostname": "broken", "repo_name": "broken"})

    with pytest.raises(StorageError, match="Invalid repository data for broken") as exc_info:
        storage.get("broken")

    assert exc_info.value.operation == "get"


def test_list_all_skips_invalid_rows(storage: DynamoDBStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    valid_repo = _make_repo()
    storage.save(valid_repo)
    storage._table.put_item(Item={"repo_path": "/broken", "hostname": "broken", "repo_name": "broken"})
    print_mock = SimpleNamespace(calls=[])

    def record(message: str) -> None:
        print_mock.calls.append(message)

    monkeypatch.setattr("borgboi.storage.dynamodb.console.print", record)

    repos = storage.list_all()

    assert [repo.name for repo in repos] == [valid_repo.name]
    assert len(print_mock.calls) == 1
    assert "Skipping repo '/broken'" in print_mock.calls[0]


def test_delete_and_exists_round_trip(storage: DynamoDBStorage) -> None:
    repo = _make_repo()
    storage.save(repo)

    assert storage.exists(repo.name) is True

    storage.delete(repo.name)

    assert storage.exists(repo.name) is False


def test_delete_by_path_raises_when_repo_missing(storage: DynamoDBStorage) -> None:
    with pytest.raises(RepositoryNotFoundError, match="not found"):
        storage.delete_by_path("/missing", hostname="host-a")


def test_exists_returns_false_when_query_raises(monkeypatch: pytest.MonkeyPatch, storage: DynamoDBStorage) -> None:
    fake_table = SimpleNamespace(query=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(DynamoDBStorage, "_table", property(lambda self: fake_table))

    assert storage.exists("repo-one") is False


def test_save_wraps_backend_errors(monkeypatch: pytest.MonkeyPatch, storage: DynamoDBStorage) -> None:
    fake_table = SimpleNamespace(put_item=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("write failed")))
    monkeypatch.setattr(DynamoDBStorage, "_table", property(lambda self: fake_table))

    with pytest.raises(StorageError, match="Failed to save repository repo-one") as exc_info:
        storage.save(_make_repo())

    assert exc_info.value.operation == "save"
