from pathlib import Path

from borgboi.clients.borg import BORGBOI_DIR_NAME
from borgboi.models import BorgBoiRepo

METADATA_DIR_NAME = ".borgboi_metadata"
metadata_dir = Path.home() / Path(BORGBOI_DIR_NAME) / METADATA_DIR_NAME


def get_repo_metadata(repo_name: str) -> BorgBoiRepo | None:
    """
    Retrieve BorgBoi repository metadata from offline storage.

    This function is a placeholder for the actual implementation that would
    retrieve the metadata of a BorgBoi repository from an offline storage system.

    Args:
        repo_name (str): The name of the BorgBoi repository.

    Returns:
        BorgBoiRepo | None: The BorgBoi repository object if found, otherwise None.
    """
    metadata_file = metadata_dir / f"{repo_name}.json"
    if metadata_file.exists():
        with metadata_file.open("r") as f:
            return BorgBoiRepo.model_validate_json(f.read())
    return None


def store_borgboi_repo_metadata(repo: BorgBoiRepo) -> None:
    """
    Store BorgBoi repository metadata in offline storage.

    This function is a placeholder for the actual implementation that would
    store the metadata of a BorgBoi repository in an offline storage system.

    Args:
        repo (BorgBoiRepo): The BorgBoi repository object containing metadata to store.
    """
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_file = metadata_dir / f"{repo.name}.json"
    with metadata_file.open("w") as f:
        _ = f.write(repo.model_dump_json(indent=2))
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
    metadata: BorgBoiRepo | None = get_repo_metadata(repo_name)
    if metadata is None:
        raise ValueError(f"Repository '{repo_name}' not found in offline storage")
    return metadata
