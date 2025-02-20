import os
import shutil
import socket
from pathlib import Path
from platform import system

from rich.table import Table

from borgboi import dynamodb, validator
from borgboi.backups import BORGBOI_DIR_NAME, EXCLUDE_FILENAME, BorgRepo
from borgboi.rich_utils import console, output_repo_info


def _get_excludes_path(repo_name: str) -> Path:
    return Path.home() / BORGBOI_DIR_NAME / f"{repo_name}_{EXCLUDE_FILENAME}"


def create_excludes_list(repo_name: str, excludes_source_file: str) -> Path:
    """
    Create the Borg exclude list.
    """
    if validator.exclude_list_created(repo_name) is True:
        raise ValueError("Exclude list already created")
    borgboi_dir = Path.home() / BORGBOI_DIR_NAME
    if borgboi_dir.exists() is False:
        borgboi_dir.mkdir()
    console.print("Creating Borg exclude list...")

    src_file = Path(excludes_source_file)
    dest_file = _get_excludes_path(repo_name)
    shutil.copy(src_file, dest_file.as_posix())

    if dest_file.exists():
        console.print(f"Exclude list created at [bold cyan]{dest_file.as_posix()}[/]")
    else:
        raise FileNotFoundError("Excludes list not created")
    return dest_file


def create_borg_repo(path: str, backup_path: str, passphrase_env_var_name: str, name: str) -> BorgRepo:
    if os.getenv("BORG_NEW_PASSPHRASE") is None:
        raise ValueError("Environment variable BORG_NEW_PASSPHRASE must be set")
    repo_path = Path(path)
    if repo_path.is_file():
        raise ValueError(f"Path {repo_path} is a file, not a directory")
    if not repo_path.exists():
        repo_path.mkdir()

    new_repo = BorgRepo(
        path=repo_path.as_posix(),
        backup_target=backup_path,
        passphrase_env_var_name=passphrase_env_var_name,
        name=name,
        hostname=socket.gethostname(),
        os_platform=system(),
    )
    if "/private/var/" in repo_path.parts or "tmp" in repo_path.parts:
        new_repo.init_repository(config_additional_free_space=False)
    else:
        new_repo.init_repository()

    dynamodb.add_repo_to_table(new_repo)
    return new_repo


def delete_borg_repo(repo_path: str | None, repo_name: str | None, dry_run: bool) -> None:
    repo = lookup_repo(repo_path, repo_name)
    if validator.repo_is_local(repo) is False:
        raise ValueError("Repository must be local to delete")
    repo.delete(dry_run)
    if not dry_run:
        dynamodb.delete_repo(repo)


def lookup_repo(repo_path: str | None, repo_name: str | None) -> BorgRepo:
    if repo_path is not None:
        return dynamodb.get_repo_by_path(repo_path)
    elif repo_name is not None:
        return dynamodb.get_repo_by_name(repo_name)
    else:
        raise ValueError("Either repo_name or repo_path must be provided")


def get_repo_info(repo_path: str | None, repo_name: str | None, pretty_print: bool) -> None:
    repo = lookup_repo(repo_path, repo_name)
    if validator.repo_is_local(repo) is False:
        raise ValueError("Repository must be local to view info")
    if pretty_print is False:
        repo.info()
    repo.collect_json_info()
    if pretty_print is True:
        if repo.metadata is None:
            raise ValueError("Repo metadata is None")
        output_repo_info(
            name=repo.name,
            total_size_gb=repo.metadata.cache.total_size_gb,
            total_csize_gb=repo.metadata.cache.total_csize_gb,
            unique_csize_gb=repo.metadata.cache.unique_csize_gb,
            encryption_mode=repo.metadata.encryption.mode,
            repo_id=repo.metadata.repository.id,
            repo_location=repo.metadata.repository.location,
            last_modified=repo.metadata.repository.last_modified,
        )
    dynamodb.update_repo(repo)


def list_repos() -> None:
    repos = dynamodb.get_all_repos()
    table = Table(title="BorgBoi Repositories", show_lines=True)
    table.add_column("Name")
    table.add_column("Local Path 📁")
    table.add_column("Hostname 🖥")
    table.add_column("Last Archive 📆")
    table.add_column("Size 💾", justify="right")
    table.add_column("Backup Target 🎯")

    for repo in repos:
        name = f"[bold cyan]{repo.name}[/]"
        local_path = f"[bold blue]{repo.repo_posix_path}[/]"
        env_var_name = f"[bold green]{repo.hostname}[/]"
        backup_target = f"[bold magenta]{repo.backup_target_posix_path}[/]"
        if repo.last_backup:
            archive_date = f"[bold yellow]{repo.last_backup.strftime('%a %b %d, %Y')}[/]"
        else:
            archive_date = "[italic red]Never[/]"
        size = (
            f"[dark_orange]{repo.unique_csize_gb:.2f} GB[/]"
            if repo.unique_csize_gb != 0.0
            else "🤷[italic red]Unknown[/]"
        )
        table.add_row(name, local_path, env_var_name, archive_date, size, backup_target)
    console.print(table)


def list_archives(repo_path: str | None, repo_name: str | None) -> None:
    """
    Retrieves Borg repo and lists all archives present within it.
    """
    repo = lookup_repo(repo_path, repo_name)
    repo.get_archives()
    console.rule(f"[bold]Archives for {repo.name}[/]")
    for archive in repo.archives:
        console.print(f"↳ [bold cyan]{archive.name}[/]")
    console.rule()


def perform_daily_backup(repo_path: str) -> None:
    repo = lookup_repo(repo_path, None)
    if validator.exclude_list_created(repo.name) is False:
        raise ValueError("Exclude list must be created before performing a backup")
    repo.create_archive()
    repo.prune()
    repo.compact()
    repo.sync_with_s3()
    repo.collect_json_info()
    dynamodb.update_repo(repo)


def restore_archive(repo_path: str, archive_name: str) -> None:
    repo = lookup_repo(repo_path, None)
    repo.extract(archive_name)


def delete_archive(repo_path: str, archive_name: str, dry_run: bool) -> None:
    repo = lookup_repo(repo_path, None)
    repo.delete_archive(archive_name, dry_run)
    if not dry_run:
        # NOTE: Space is NOT reclaimed on disk until the 'compact' command is ran
        repo.compact()
