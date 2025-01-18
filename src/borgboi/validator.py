import socket

from borgboi.backups import BorgRepo


def repo_is_local(repo: BorgRepo) -> bool:
    return repo.hostname == socket.gethostname()
