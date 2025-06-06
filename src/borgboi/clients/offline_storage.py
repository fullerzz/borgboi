from pathlib import Path

from borgboi.clients.borg import BORGBOI_DIR_NAME
from borgboi.clients.utils import trash
from borgboi.models import BorgBoiRepo

METADATA_DIR_NAME = ".borgboi_metadata"
METADATA_DIR: Path = Path.home() / Path(BORGBOI_DIR_NAME) / METADATA_DIR_NAME


def _get_repo_metadata(repo_name: str) -> BorgBoiRepo | None:
    """
    Retrieve BorgBoi repository metadata from offline storage.

    This function is a placeholder for the actual implementation that would
    retrieve the metadata of a BorgBoi repository from an offline storage system.

    Args:
        repo_name (str): The name of the BorgBoi repository.

    Returns:
        BorgBoiRepo | None: The BorgBoi repository object if found, otherwise None.
    """
    metadata_file = METADATA_DIR / f"{repo_name}.json"
    if metadata_file.exists():
        with metadata_file.open("r") as f:
            return BorgBoiRepo.model_validate_json(f.read())
    return None


def get_repo(repo_name: str | None = None) -> BorgBoiRepo:
    """
    Retrieve a BorgBoi repository by name from offline storage.

    Args:
        repo_name (str | None): The name of the BorgBoi repository.

    Returns:
        BorgBoiRepo | None: The BorgBoi repository object if found, otherwise None.
    """
    if not repo_name:
        raise ValueError("repo_name must be provided to retrieve a BorgBoi repository in offline mode")
    metadata: BorgBoiRepo | None = _get_repo_metadata(repo_name)
    if metadata is None:
        raise ValueError(f"Repository '{repo_name}' not found in offline storage")
    return metadata


def store_borgboi_repo_metadata(repo: BorgBoiRepo) -> None:
    """
    Store BorgBoi repository metadata in offline storage.

    This function is a placeholder for the actual implementation that would
    store the metadata of a BorgBoi repository in an offline storage system.

    Args:
        repo (BorgBoiRepo): The BorgBoi repository object containing metadata to store.
    """
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    metadata_file = METADATA_DIR / f"{repo.name}.json"
    with metadata_file.open("w") as f:
        _ = f.write(repo.model_dump_json(indent=2))
    return None


def delete_repo_metadata(repo_name: str) -> None:
    """
    Delete BorgBoi repository metadata from offline storage.
    """
    metadata_file = METADATA_DIR / f"{repo_name}.json"
    try:
        trash.trash_file(metadata_file)
    except trash.TrashError as e:
        # TODO: Potentially allow force deletion without trashing
        # For now, we will raise an error if trashing fails
        raise RuntimeError(f"Failed to delete {repo_name} metadata") from e
