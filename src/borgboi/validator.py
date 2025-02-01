import socket
from pathlib import Path

from borgboi.backups import BORGBOI_DIR_NAME, EXCLUDE_FILENAME, BorgRepo


def repo_is_local(repo: BorgRepo) -> bool:
    return repo.hostname == socket.gethostname()


def exclude_list_created(repo_name: str) -> bool:
    exclude_file = Path.home() / BORGBOI_DIR_NAME / f"{repo_name}_{EXCLUDE_FILENAME}"
    return exclude_file.exists()
