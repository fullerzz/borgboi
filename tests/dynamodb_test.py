from pathlib import Path
from platform import system

import pytest
from mypy_boto3_dynamodb import DynamoDBClient

from borgboi.models import BorgBoiRepo

from .conftest import DYNAMO_ARCHIVES_TABLE_NAME, DYNAMO_TABLE_NAME


def get_mock_metadata(repo_path: Path) -> str:
    """Return a mock JSON string representing a Borg repository's metadata."""
    from borgboi.clients.borg import Encryption, RepoCache, RepoInfo, Repository, Stats

    repo_info = RepoInfo(
        cache=RepoCache(
            path="/path/to/cache",
            stats=Stats(
                total_chunks=100,
                total_size=1000,
                total_csize=500,
                total_unique_chunks=50,
                unique_csize=500,
                unique_size=1000,
            ),
        ),
        encryption=Encryption(mode="repokey"),
        repository=Repository(id="1234", last_modified="2025-01-01", location=repo_path.as_posix()),
        security_dir="/path/to/security",
    )
    return repo_info.model_dump_json()


@pytest.fixture
def borgboi_repo(repo_storage_dir: Path, backup_target_dir: Path) -> BorgBoiRepo:
    from borgboi.clients.borg import RepoInfo

    metadata_json_str = get_mock_metadata(repo_storage_dir)
    return BorgBoiRepo(
        path=repo_storage_dir.as_posix(),
        backup_target=backup_target_dir.as_posix(),
        name="test-repo",
        hostname="test-host",
        os_platform=system(),
        metadata=RepoInfo.model_validate_json(metadata_json_str),
    )


@pytest.mark.usefixtures("create_dynamodb_table")
def test_add_repo_to_table(dynamodb: DynamoDBClient, borgboi_repo: BorgBoiRepo) -> None:
    from borgboi.clients.dynamodb import add_repo_to_table

    add_repo_to_table(borgboi_repo)

    response = dynamodb.get_item(
        TableName=DYNAMO_TABLE_NAME,
        Key={"repo_path": {"S": borgboi_repo.path}, "hostname": {"S": borgboi_repo.hostname}},
    )
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.path  # pyright: ignore[reportTypedDictNotRequiredAccess]


@pytest.mark.usefixtures("create_dynamodb_table")
def test_update_repo(dynamodb: DynamoDBClient, borgboi_repo: BorgBoiRepo) -> None:
    from borgboi.clients.dynamodb import add_repo_to_table, get_repo_by_path, update_repo

    new_name = "updated-test-repo-name"
    original_hostname = borgboi_repo.hostname

    # Populate test table with initial repo
    add_repo_to_table(borgboi_repo)
    response = dynamodb.get_item(
        TableName=DYNAMO_TABLE_NAME,
        Key={"repo_path": {"S": borgboi_repo.path}, "hostname": {"S": borgboi_repo.hostname}},
    )
    assert "Item" in response
    assert response["Item"]["repo_path"]["S"] == borgboi_repo.path  # pyright: ignore[reportTypedDictNotRequiredAccess]

    # Update repo name field and call update_repo(...)
    borgboi_repo.name = new_name
    update_repo(borgboi_repo)

    # Verify that the repo was updated in the table
    repo_from_table = get_repo_by_path(borgboi_repo.path, original_hostname)
    assert repo_from_table.name == new_name
    assert repo_from_table.hostname == original_hostname
    # Compare excluding metadata (not stored in table, fetched fresh for local repos)
    assert repo_from_table.model_dump(exclude={"metadata", "safe_path"}) == borgboi_repo.model_dump(
        exclude={"metadata", "safe_path"}
    )


# ============================================================================
# Archive Table Tests
# ============================================================================


@pytest.fixture
def sample_archive_item():
    """Return a sample BorgBoiArchiveTableItem for testing."""
    from borgboi.clients.dynamodb import BorgBoiArchiveTableItem

    return BorgBoiArchiveTableItem(
        repo_name="test-repo",
        iso_timestamp="2025-01-10T12:00:00",
        archive_id="abc123def456",
        archive_name="2025-01-10_12:00:00",
        archive_path="/path/to/repo::2025-01-10_12:00:00",
        hostname="test-host",
        original_size=1000000,
        compressed_size=500000,
        deduped_size=250000,
    )


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_add_archive_to_table(dynamodb: DynamoDBClient, sample_archive_item) -> None:
    from borgboi.clients.dynamodb import add_archive_to_table

    add_archive_to_table(sample_archive_item)

    response = dynamodb.get_item(
        TableName=DYNAMO_ARCHIVES_TABLE_NAME,
        Key={
            "repo_name": {"S": sample_archive_item.repo_name},
            "iso_timestamp": {"S": sample_archive_item.iso_timestamp},
        },
    )
    assert "Item" in response
    assert response["Item"]["archive_id"]["S"] == sample_archive_item.archive_id


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_get_archives_by_repo(dynamodb: DynamoDBClient, sample_archive_item) -> None:
    from borgboi.clients.dynamodb import add_archive_to_table, get_archives_by_repo

    add_archive_to_table(sample_archive_item)

    archives = get_archives_by_repo(sample_archive_item.repo_name)
    assert len(archives) == 1
    assert archives[0].archive_id == sample_archive_item.archive_id
    assert archives[0].repo_name == sample_archive_item.repo_name


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_get_archives_by_repo_empty(dynamodb: DynamoDBClient) -> None:
    from borgboi.clients.dynamodb import get_archives_by_repo

    archives = get_archives_by_repo("nonexistent-repo")
    assert len(archives) == 0


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_get_archive_by_id(dynamodb: DynamoDBClient, sample_archive_item) -> None:
    from borgboi.clients.dynamodb import add_archive_to_table, get_archive_by_id

    add_archive_to_table(sample_archive_item)

    archive = get_archive_by_id(sample_archive_item.archive_id)
    assert archive is not None
    assert archive.repo_name == sample_archive_item.repo_name
    assert archive.archive_name == sample_archive_item.archive_name


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_get_archive_by_id_not_found(dynamodb: DynamoDBClient) -> None:
    from borgboi.clients.dynamodb import get_archive_by_id

    archive = get_archive_by_id("nonexistent-id")
    assert archive is None


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_get_archives_by_hostname(dynamodb: DynamoDBClient, sample_archive_item) -> None:
    from borgboi.clients.dynamodb import add_archive_to_table, get_archives_by_hostname

    add_archive_to_table(sample_archive_item)

    archives = get_archives_by_hostname(sample_archive_item.hostname)
    assert len(archives) == 1
    assert archives[0].archive_id == sample_archive_item.archive_id


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_delete_archive(dynamodb: DynamoDBClient, sample_archive_item) -> None:
    from borgboi.clients.dynamodb import add_archive_to_table, delete_archive, get_archives_by_repo

    add_archive_to_table(sample_archive_item)

    # Verify archive exists
    archives = get_archives_by_repo(sample_archive_item.repo_name)
    assert len(archives) == 1

    # Delete and verify
    delete_archive(sample_archive_item.repo_name, sample_archive_item.iso_timestamp)
    archives = get_archives_by_repo(sample_archive_item.repo_name)
    assert len(archives) == 0


@pytest.mark.usefixtures("create_dynamodb_archives_table")
def test_multiple_archives_same_repo(dynamodb: DynamoDBClient, sample_archive_item) -> None:
    from borgboi.clients.dynamodb import BorgBoiArchiveTableItem, add_archive_to_table, get_archives_by_repo

    # Add first archive
    add_archive_to_table(sample_archive_item)

    # Add second archive with different timestamp
    second_archive = BorgBoiArchiveTableItem(
        repo_name=sample_archive_item.repo_name,
        iso_timestamp="2025-01-11T12:00:00",
        archive_id="xyz789",
        archive_name="2025-01-11_12:00:00",
        archive_path="/path/to/repo::2025-01-11_12:00:00",
        hostname=sample_archive_item.hostname,
        original_size=2000000,
        compressed_size=1000000,
        deduped_size=500000,
    )
    add_archive_to_table(second_archive)

    # Verify both archives are retrieved
    archives = get_archives_by_repo(sample_archive_item.repo_name)
    assert len(archives) == 2
    archive_ids = {a.archive_id for a in archives}
    assert sample_archive_item.archive_id in archive_ids
    assert second_archive.archive_id in archive_ids
