from pathlib import Path

from borgboi.clients.utils import trash
from borgboi.config import config
from borgboi.core.logging import get_logger
from borgboi.models import BorgBoiRepo

METADATA_DIR_NAME = ".borgboi_metadata"
METADATA_DIR: Path = config.borgboi_dir / METADATA_DIR_NAME
logger = get_logger(__name__)


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
    logger.debug("Loading offline repository metadata", repo_name=repo_name, metadata_file=str(metadata_file))
    if metadata_file.exists():
        with metadata_file.open("r") as f:
            metadata = BorgBoiRepo.model_validate_json(f.read())
        logger.debug("Loaded offline repository metadata", repo_name=repo_name, metadata_file=str(metadata_file))
        return metadata
    logger.debug("Offline repository metadata not found", repo_name=repo_name, metadata_file=str(metadata_file))
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
        logger.error("Offline repository lookup missing repository name")
        raise ValueError("repo_name must be provided to retrieve a BorgBoi repository in offline mode")
    logger.debug("Getting repository from offline storage", repo_name=repo_name)
    metadata: BorgBoiRepo | None = _get_repo_metadata(repo_name)
    if metadata is None:
        logger.warning("Repository not found in offline storage", repo_name=repo_name)
        raise ValueError(f"Repository '{repo_name}' not found in offline storage")
    logger.debug("Retrieved repository from offline storage", repo_name=repo_name, repo_path=metadata.path)
    return metadata


def store_borgboi_repo_metadata(repo: BorgBoiRepo) -> None:
    """
    Store BorgBoi repository metadata in offline storage.

    This function is a placeholder for the actual implementation that would
    store the metadata of a BorgBoi repository in an offline storage system.

    Args:
        repo (BorgBoiRepo): The BorgBoi repository object containing metadata to store.
    """
    logger.info("Storing offline repository metadata", repo_name=repo.name, repo_path=repo.path)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    metadata_file = METADATA_DIR / f"{repo.name}.json"
    with metadata_file.open("w") as f:
        _ = f.write(repo.model_dump_json(indent=2))
    logger.info("Stored offline repository metadata", repo_name=repo.name, metadata_file=str(metadata_file))
    return None


def delete_repo_metadata(repo_name: str) -> None:
    """
    Delete BorgBoi repository metadata from offline storage.
    """
    metadata_file = METADATA_DIR / f"{repo_name}.json"
    logger.info("Deleting offline repository metadata", repo_name=repo_name, metadata_file=str(metadata_file))
    try:
        trash.trash_file(metadata_file)
    except trash.TrashError as e:
        logger.error(
            "Failed to delete offline repository metadata",
            repo_name=repo_name,
            metadata_file=str(metadata_file),
            error=str(e),
        )
        # TODO: Potentially allow force deletion without trashing
        # For now, we will raise an error if trashing fails
        raise RuntimeError(f"Failed to delete {repo_name} metadata") from e
    logger.info("Deleted offline repository metadata", repo_name=repo_name, metadata_file=str(metadata_file))
