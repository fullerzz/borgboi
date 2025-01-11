from borgboi.backups import BorgRepo
from borgboi.dynamodb import get_repo_by_name, get_repo_by_path


def lookup_repo(repo_name: str | None, repo_path: str | None) -> BorgRepo:
    if repo_path is not None:
        return get_repo_by_path(repo_path)
    elif repo_name is not None:
        return get_repo_by_name(repo_name)
    else:
        raise ValueError("Either repo_name or repo_path must be provided")
