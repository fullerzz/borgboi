from pathlib import Path

from borgboi.backups import BorgRepo
from borgboi.dynamodb import get_repo_by_name, get_repo_by_path, update_repo


def create_borg_repo(path: str, passphrase_env_var_name: str, name: str) -> BorgRepo:
    repo_path = Path(path)
    if repo_path.is_file():
        raise ValueError(f"Path {repo_path} is a file, not a directory")
    if not repo_path.exists():
        repo_path.mkdir()
    return BorgRepo(path=repo_path, passphrase_env_var_name=passphrase_env_var_name, name=name)


def lookup_repo(repo_path: str | None, repo_name: str | None) -> BorgRepo:
    if repo_path is not None:
        return get_repo_by_path(repo_path)
    elif repo_name is not None:
        return get_repo_by_name(repo_name)
    else:
        raise ValueError("Either repo_name or repo_path must be provided")


def perform_daily_backup(repo_path: str) -> None:
    repo = lookup_repo(repo_path, None)
    dir_to_backup = Path.home()
    repo.create_archive(dir_to_backup=dir_to_backup)
    repo.prune()
    repo.compact()
    repo.sync_with_s3()
    update_repo(repo)
