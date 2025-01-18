import os
import socket
from pathlib import Path

from rich.table import Table

from borgboi.backups import BorgRepo
from borgboi.dynamodb import add_repo_to_table, get_all_repos, get_repo_by_name, get_repo_by_path, update_repo
from borgboi.rich_utils import console


def create_borg_repo(path: str, backup_path: str, passphrase_env_var_name: str, name: str) -> BorgRepo:
    if os.getenv("BORG_NEW_PASSPHRASE") is None:
        raise ValueError("Environment variable BORG_NEW_PASSPHRASE must be set")
    repo_path = Path(path)
    if repo_path.is_file():
        raise ValueError(f"Path {repo_path} is a file, not a directory")
    if not repo_path.exists():
        repo_path.mkdir()

    new_repo = BorgRepo(
        path=repo_path,
        backup_target=Path(backup_path),
        passphrase_env_var_name=passphrase_env_var_name,
        name=name,
        hostname=socket.gethostname(),
    )
    new_repo.init_repository()
    add_repo_to_table(new_repo)
    return new_repo


def lookup_repo(repo_path: str | None, repo_name: str | None) -> BorgRepo:
    if repo_path is not None:
        return get_repo_by_path(repo_path)
    elif repo_name is not None:
        return get_repo_by_name(repo_name)
    else:
        raise ValueError("Either repo_name or repo_path must be provided")


def list_repos() -> None:
    repos = get_all_repos()
    table = Table(title="BorgBoi Repositories", show_lines=True)
    table.add_column("Name")
    table.add_column("Local Path")
    table.add_column("Passphrase Environment Variable")
    table.add_column("Last Archive Date")
    table.add_column("Last S3 Sync Date")
    table.add_column("Archival Target")

    for repo in repos:
        name = f"[bold cyan]{repo.name}[/]"
        local_path = f"[bold blue]{repo.path.as_posix()}[/]"
        env_var_name = f"[bold green]{repo.passphrase_env_var_name}[/]"
        if repo.last_backup:
            archive_date = f"[bold yellow]{repo.last_backup.strftime('%a %b %d, %Y')}[/]"
        else:
            archive_date = "[italic red]Never[/]"
        if repo.last_s3_sync:
            sync_date = f"[bold yellow]{repo.last_s3_sync.strftime('%a %b %d, %Y')}[/]"
        else:
            sync_date = "[italic red]Never[/]"
        table.add_row(name, local_path, env_var_name, archive_date, sync_date)
    console.print(table)


def perform_daily_backup(repo_path: str) -> None:
    repo = lookup_repo(repo_path, None)
    repo.create_archive()
    repo.prune()
    repo.compact()
    repo.sync_with_s3()
    update_repo(repo)
