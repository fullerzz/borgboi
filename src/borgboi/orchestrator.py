import os
import shutil
import socket
from pathlib import Path
from platform import system

import rich
from rich.table import Table
import rich.text

from borgboi import validator
from borgboi.clients import borg, dynamodb, s3
from borgboi.models import BORGBOI_DIR_NAME, EXCLUDE_FILENAME, BorgBoiRepo
from borgboi.rich_utils import console, output_repo_info, render_cmd_output_lines


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


def create_borg_repo(path: str, backup_path: str, name: str) -> BorgBoiRepo:
    if os.getenv("BORG_NEW_PASSPHRASE") is None:
        raise ValueError("Environment variable BORG_NEW_PASSPHRASE must be set")
    repo_path = Path(path)
    if repo_path.is_file():
        raise ValueError(f"Path {repo_path} is a file, not a directory")
    if not repo_path.exists():
        repo_path.mkdir()

    if "/private/var/" in repo_path.parts or "tmp" in repo_path.parts:
        borg.init_repository(repo_path.as_posix(), config_additional_free_space=False)
    else:
        borg.init_repository(repo_path.as_posix())

    repo_info = borg.info(repo_path.as_posix())
    borgboi_repo = BorgBoiRepo(
        path=repo_path.as_posix(),
        backup_target=backup_path,
        name=name,
        hostname=socket.gethostname(),
        os_platform=system(),
        metadata=repo_info,
    )
    dynamodb.add_repo_to_table(borgboi_repo)
    return borgboi_repo


def delete_borg_repo(repo_path: str | None, repo_name: str | None, dry_run: bool) -> None:
    """
    Delete a Borg repository.

    Raises:
        ValueError: Repository must be local to delete
    """
    repo = lookup_repo(repo_path, repo_name)
    if not validator.repo_is_local(repo):
        raise ValueError("Repository must be local to delete")
    for log_msg in borg.delete(repo.path, repo.name, dry_run):
        msg = validator.parse_log(log_msg)
        console.print(msg)
    if not dry_run:
        dynamodb.delete_repo(repo)
        delete_excludes_list(repo.name)


def delete_excludes_list(repo_name: str) -> None:
    """
    Delete the Borg repo's exclude list.
    """
    excludes_path = _get_excludes_path(repo_name)
    if excludes_path.exists():
        excludes_path.unlink()
        console.print(f"Deleted exclude list for [bold cyan]{repo_name}[/]")
    else:
        raise FileNotFoundError("Exclude list not found")


def lookup_repo(repo_path: str | None, repo_name: str | None) -> BorgBoiRepo:
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
        borg.info(repo.path)
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
        local_path = f"[bold blue]{repo.path}[/]"
        env_var_name = f"[bold green]{repo.hostname}[/]"
        backup_target = f"[bold magenta]{repo.backup_target}[/]"
        if repo.last_backup:
            archive_date = f"[bold yellow]{repo.last_backup.strftime('%a %b %d, %Y')}[/]"
        else:
            archive_date = "[italic red]Never[/]"
        size = (
            f"[dark_orange]{repo.metadata.cache.unique_csize_gb:.2f} GB[/]"
            if repo.metadata.cache.unique_csize_gb != 0.0
            else "🤷[italic red]Unknown[/]"
        )
        table.add_row(name, local_path, env_var_name, archive_date, size, backup_target)
    console.print(table)


def list_archives(repo_path: str | None, repo_name: str | None) -> None:
    """
    Retrieves Borg repo and lists all archives present within it.
    """
    repo = lookup_repo(repo_path, repo_name)
    archives = borg.list_archives(repo.path)
    console.rule(f"[bold]Archives for {repo.name}[/]")
    for archive in archives:
        console.print(f"↳ [bold cyan]{archive.name}[/]")
    console.rule()


def perform_daily_backup(repo_path: str) -> None:
    repo = lookup_repo(repo_path, None)
    if validator.exclude_list_created(repo.name) is False:
        raise ValueError("Exclude list must be created before performing a backup")
    for log_msg in validator.parse_logs(borg.create_archive(repo.path, repo.name, repo.backup_target)):
        console.print(log_msg)
    for log_msg in validator.parse_logs(borg.prune(repo.path)):
        console.print(log_msg)
    for log_msg in validator.parse_logs(borg.compact(repo.path)):
        console.print(log_msg)
    for msg in s3.sync_with_s3(repo.path, repo.name):
        console.print(msg)
    # Refresh metadata after backup and pruning complete
    repo.metadata = borg.info(repo.path)
    dynamodb.update_repo(repo)


def restore_archive(repo_path: str, archive_name: str) -> None:
    repo = lookup_repo(repo_path, None)
    for log_msg in borg.extract(repo.path, archive_name):
        msg = validator.parse_log(log=log_msg)
        console.print(msg)


def delete_archive(repo_path: str, archive_name: str, dry_run: bool) -> None:
    repo = lookup_repo(repo_path, None)
    for log_msg in borg.delete_archive(repo.path, repo.name, archive_name, dry_run):
        msg = validator.parse_log(log_msg)
        console.print(msg)
    if not dry_run:
        # NOTE: Space is NOT reclaimed on disk until the 'compact' command is ran
        for log_msg in borg.compact(repo.path):
            msg = validator.parse_log(log_msg)
            console.print(msg)


def extract_repo_key(repo_path: str) -> Path:
    repo = lookup_repo(repo_path, None)
    key_path = borg.export_repo_key(repo.path, repo.name)
    return key_path


def demo_v1(repo: BorgBoiRepo) -> None:
    """
    Perform a demo of the v1 backup process.
    """

    if repo.name != "GO_HOME":
        raise ValueError("Demo only works with the 'GO_HOME' repo")

    title = rich.text.Text("Creating archive", style="bold #74c7ec")
    console.rule(title, style="#c6a0f6")
    render_cmd_output_lines(
        "[bold blue]Creating new archive[/]",
        "Archive created successfully",
        borg.create_archive(repo.path, repo.name, repo.backup_target, log_json=False),
    )
    console.rule(":heavy_check_mark: [bold #a6e3a1]Archive created successfully[/]", style="#c6a0f6")

    console.print("")
    title = rich.text.Text("Pruning archive", style="bold #74c7ec")
    console.rule(title, style="#f5a97f")
    render_cmd_output_lines(
        "[bold blue]Pruning old backups[/]", "Pruning completed successfully", borg.prune(repo.path, log_json=False)
    )
    console.rule(":heavy_check_mark: [bold #a6e3a1]Pruning completed successfully[/]", style="#f5a97f")

    console.print("")
    title = rich.text.Text("Compacting archive", style="bold #74c7ec")
    console.rule(title, style="#7dc4e4")
    render_cmd_output_lines(
        "[bold blue]Compacting borg repo[/]",
        "Compacting completed successfully",
        borg.compact(repo.path, log_json=False),
    )
    console.rule(":heavy_check_mark: [bold #a6e3a1]Compacting completed successfully[/]", style="#7dc4e4")
