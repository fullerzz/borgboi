import shutil
import socket
from pathlib import Path
from platform import system

from borgboi import rich_utils, validator
from borgboi.clients import borg, dynamodb, offline_storage, s3
from borgboi.config import config
from borgboi.lib import utils
from borgboi.lib.colors import COLOR_HEX
from borgboi.lib.passphrase import (
    generate_secure_passphrase,
    migrate_repo_passphrase,
    resolve_passphrase,
    save_passphrase_to_file,
)
from borgboi.models import BorgBoiRepo
from borgboi.rich_utils import console

# DEPRECATED: Old passphrase resolution function removed.
# Now using resolve_passphrase() from borgboi.lib.passphrase module.
# New priority: CLI > File > Env > Config


def _get_excludes_path(repo_name: str) -> Path:
    return config.borgboi_dir / f"{repo_name}_{config.excludes_filename}"


def create_excludes_list(repo_name: str, excludes_source_file: str) -> Path:
    """
    Create the Borg exclude list.
    """
    if validator.exclude_list_created(repo_name) is True:
        raise ValueError("Exclude list already created")
    borgboi_dir = config.borgboi_dir
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


def create_borg_repo(
    path: str, backup_path: str, name: str, offline: bool, passphrase: str | None = None
) -> BorgBoiRepo:
    # Resolve or generate passphrase: CLI param > file > env var > config > auto-generate
    resolved_passphrase = resolve_passphrase(
        repo_name=name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
        env_var_name="BORG_NEW_PASSPHRASE",
    )

    # Auto-generate if not provided (like borgopher)
    if resolved_passphrase is None:
        resolved_passphrase = generate_secure_passphrase()
        console.print(f"[bold yellow]Generated passphrase for repo '{name}'[/]")
        console.print(f"[bold cyan]Passphrase: {resolved_passphrase}[/]")
        console.print("[bold red]SAVE THIS PASSPHRASE SECURELY![/]")

    # Save passphrase to file
    passphrase_file_path = save_passphrase_to_file(name, resolved_passphrase)
    console.print(f"[bold green]Passphrase saved to: {passphrase_file_path}[/]")

    repo_path = Path(path)
    if repo_path.is_file():
        raise ValueError(f"Path {repo_path} is a file, not a directory")
    if not repo_path.exists():
        repo_path.mkdir()

    if "/private/var/" in repo_path.parts or "tmp" in repo_path.parts:
        borg.init_repository(repo_path.as_posix(), config_additional_free_space=False, passphrase=resolved_passphrase)
    else:
        borg.init_repository(repo_path.as_posix(), passphrase=resolved_passphrase)

    repo_info = borg.info(repo_path.as_posix(), passphrase=resolved_passphrase)
    borgboi_repo = BorgBoiRepo(
        path=repo_path.as_posix(),
        backup_target=backup_path,
        name=name,
        hostname=socket.gethostname(),
        os_platform=system(),
        metadata=repo_info,
        passphrase=None,  # Don't store in DB
        passphrase_file_path=passphrase_file_path.as_posix(),
        passphrase_migrated=True,
    )
    if not offline:
        dynamodb.add_repo_to_table(borgboi_repo)
    else:
        offline_storage.store_borgboi_repo_metadata(borgboi_repo)

    return borgboi_repo


def delete_borg_repo(
    repo_path: str | None, repo_name: str | None, dry_run: bool, offline: bool, passphrase: str | None = None
) -> None:
    """
    Delete a Borg repository.

    Raises:
        ValueError: Repository must be local to delete
    """
    repo = lookup_repo(repo_path, repo_name, offline)
    if not validator.repo_is_local(repo):
        raise ValueError("Repository must be local to delete")
    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    for log_msg in borg.delete(repo.path, repo.name, dry_run, passphrase=resolved_passphrase):
        msg = validator.parse_log(log_msg)
        console.print(msg)
    if not dry_run:
        if not offline:
            dynamodb.delete_repo(repo)
        else:
            offline_storage.delete_repo_metadata(repo.name)
        delete_excludes_list(repo.name)


def delete_excludes_list(repo_name: str) -> None:
    """
    Delete the Borg repo's exclude list.
    """
    excludes_path = _get_excludes_path(repo_name)
    if excludes_path.exists():
        excludes_path.unlink()
        console.print(f"Deleted exclude list for [bold cyan]{repo_name}[/]")


def _auto_migrate_repo_passphrase_if_needed(repo: BorgBoiRepo, offline: bool) -> BorgBoiRepo:
    """Auto-migrate repo passphrase to file if needed (hybrid approach).

    Args:
        repo: Repository to potentially migrate
        offline: Whether in offline mode

    Returns:
        BorgBoiRepo: Updated repository (may be same as input if no migration needed)
    """
    # Skip if already migrated or no passphrase to migrate
    if repo.passphrase_migrated or repo.passphrase is None:
        return repo

    # Notify user of auto-migration
    console.print(f"[bold yellow]Auto-migrating passphrase for repo '{repo.name}' to file storage...[/]")

    try:
        passphrase_file_path = migrate_repo_passphrase(repo.name, repo.passphrase)
        repo.passphrase_file_path = passphrase_file_path.as_posix()
        repo.passphrase_migrated = True
        # Keep repo.passphrase for backward compatibility (don't clear)

        # Update database
        if not offline:
            dynamodb.update_repo(repo)
        else:
            offline_storage.store_borgboi_repo_metadata(repo)

        console.print(f"[bold green]✓ Passphrase migrated to {passphrase_file_path}[/]")
    except Exception as e:
        console.print(f"[bold red]Failed to auto-migrate passphrase: {e}[/]")
        console.print("[bold yellow]Run 'bb migrate-passphrases' to migrate manually[/]")

    return repo


def migrate_repo_passphrase_to_file(repo: BorgBoiRepo, offline: bool) -> BorgBoiRepo:
    """Manually migrate a repository's passphrase from database to file storage.

    Args:
        repo: Repository to migrate
        offline: Whether in offline mode

    Returns:
        BorgBoiRepo: Updated repository

    Raises:
        ValueError: If repo already migrated or has no passphrase
    """
    if repo.passphrase_migrated:
        console.print(f"[bold yellow]Repository {repo.name} already migrated[/]")
        return repo

    if repo.passphrase is None:
        raise ValueError(f"Repository {repo.name} has no passphrase to migrate")

    # Migrate passphrase to file
    passphrase_file_path = migrate_repo_passphrase(repo.name, repo.passphrase)

    # Update repo
    repo.passphrase_file_path = passphrase_file_path.as_posix()
    repo.passphrase_migrated = True
    # Keep repo.passphrase for backward compatibility

    # Update database
    if not offline:
        dynamodb.update_repo(repo)
    else:
        offline_storage.store_borgboi_repo_metadata(repo)

    console.print(f"[bold green]✓ Migrated passphrase for {repo.name} to {passphrase_file_path}[/]")
    return repo


def lookup_repo(
    repo_path: str | None, repo_name: str | None, offline: bool, hostname: str | None = None
) -> BorgBoiRepo:
    if offline:
        repo = offline_storage.get_repo(repo_name)
    elif repo_path is not None:
        repo = dynamodb.get_repo_by_path(repo_path, hostname) if hostname else dynamodb.get_repo_by_path(repo_path)
    elif repo_name is not None:
        repo = dynamodb.get_repo_by_name(repo_name)
    else:
        raise ValueError("Either repo_name or repo_path must be provided")

    # Auto-migrate if needed (hybrid approach)
    repo = _auto_migrate_repo_passphrase_if_needed(repo, offline)

    return repo


def get_repo_info(
    repo_path: str | None, repo_name: str | None, pretty_print: bool, offline: bool, passphrase: str | None = None
) -> None:
    repo = lookup_repo(repo_path, repo_name, offline)
    if validator.repo_is_local(repo) is False:
        raise ValueError("Repository must be local to view info")
    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    if pretty_print is False:
        borg.info(repo.path, passphrase=resolved_passphrase)
    if pretty_print is True:
        if repo.metadata is None:
            raise ValueError("Repo metadata is None")
        rich_utils.output_repo_info(
            name=repo.name,
            total_size_gb=repo.metadata.cache.total_size_gb,
            total_csize_gb=repo.metadata.cache.total_csize_gb,
            unique_csize_gb=repo.metadata.cache.unique_csize_gb,
            encryption_mode=repo.metadata.encryption.mode,
            repo_id=repo.metadata.repository.id,
            repo_location=repo.metadata.repository.location,
            last_modified=repo.metadata.repository.last_modified,
        )
    if not offline:
        dynamodb.update_repo(repo)


def list_repos_data(offline: bool) -> list[BorgBoiRepo]:
    """Get list of all repositories without outputting to console.

    Args:
        offline: Whether in offline mode

    Returns:
        list[BorgBoiRepo]: List of all repositories
    """
    if offline:
        # For offline mode, we need to get repos one by one
        # This is a placeholder - offline mode bulk operations not yet implemented
        raise NotImplementedError("Bulk migration not yet supported in offline mode")
    else:
        return dynamodb.get_all_repos()


def list_repos(offline: bool) -> None:
    """List all repositories and output to console.

    Args:
        offline: Whether in offline mode
    """
    if offline:
        # Placeholder for listing offline repos
        console.print("Listing repositories in offline mode is not yet implemented.")
        return
    repos = dynamodb.get_all_repos()
    rich_utils.output_repos_table(repos)


def list_archives(repo_path: str | None, repo_name: str | None, offline: bool, passphrase: str | None = None) -> None:
    """
    Retrieves Borg repo and lists all archives present within it.
    """
    repo = lookup_repo(repo_path, repo_name, offline)
    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    archives = borg.list_archives(repo.path, passphrase=resolved_passphrase)
    archives.sort(key=lambda x: x.name, reverse=True)
    console.rule(f"[bold]Archives for {repo.name}[/]")
    for archive in archives:
        console.print(
            f"↳ [bold {COLOR_HEX.sky}]{archive.name}[/]\t[bold {COLOR_HEX.green}]Age: {utils.calculate_archive_age(archive.name)}[/]\t[{COLOR_HEX.mauve}]ID: {archive.id}[/]"
        )
    console.rule()


def list_archive_contents(
    repo_path: str | None,
    repo_name: str | None,
    archive_name: str,
    output_file: str = "stdout",
    offline: bool = False,
    passphrase: str | None = None,
) -> None:
    """
    Lists the contents of a specific Borg archive.
    """
    repo = lookup_repo(repo_path, repo_name, offline)
    if not validator.repo_is_local(repo):
        raise ValueError("Repository must be local to list archive contents")
    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    contents = borg.list_archive_contents(repo.path, archive_name, passphrase=resolved_passphrase)

    if output_file == "stdout":
        output_lines = [f"↳ [bold {COLOR_HEX.sky}]{utils.shorten_archive_path(item.path)}[/]" for item in contents]
    else:
        output_lines = [f"{item.path}" for item in contents]  # Use original path for file output

    if output_file == "stdout":
        for line in output_lines:
            console.print(line)
        console.rule()
    else:
        output_path = Path(output_file)
        with output_path.open("w") as f:
            for line in output_lines:
                _ = f.write(line + "\n")  # No prefix to remove
        console.print(f"Archive contents written to [bold cyan]{output_path.as_posix()}[/]")


def perform_daily_backup(repo_path: str, offline: bool, passphrase: str | None = None) -> None:
    repo = lookup_repo(repo_path, None, offline)
    if validator.exclude_list_created(repo.name) is False:
        raise ValueError("Exclude list must be created before performing a backup")
    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    # create archive
    rich_utils.render_cmd_output_lines(
        "Creating new archive",
        "Archive created successfully",
        borg.create_archive(repo.path, repo.name, repo.backup_target, log_json=False, passphrase=resolved_passphrase),
        ruler_color=COLOR_HEX.mauve,
    )

    # prune
    rich_utils.render_cmd_output_lines(
        "Pruning old backups",
        "Pruning completed successfully",
        borg.prune(repo.path, log_json=False, passphrase=resolved_passphrase),
        ruler_color=COLOR_HEX.peach,
    )

    # compact
    rich_utils.render_cmd_output_lines(
        "Compacting borg repo",
        "Compacting completed successfully",
        borg.compact(repo.path, log_json=False, passphrase=resolved_passphrase),
        spinner="dots",
        ruler_color=COLOR_HEX.sapphire,
    )

    if not offline:
        # sync with s3 and update dynamodb
        rich_utils.render_cmd_output_lines(
            "Syncing repo with S3 bucket",
            "S3 sync completed successfully",
            s3.sync_with_s3(repo.path, repo.name),
            spinner="arrow",
            ruler_color=COLOR_HEX.green,
        )

        # Refresh metadata after backup and pruning complete
        repo.metadata = borg.info(repo.path, passphrase=resolved_passphrase)
        dynamodb.update_repo(repo)
    else:
        # In offline mode, just update local metadata
        repo.metadata = borg.info(repo.path, passphrase=resolved_passphrase)
        offline_storage.store_borgboi_repo_metadata(repo)


def restore_repo(repo: BorgBoiRepo, dry_run: bool, force: bool = False, offline: bool = False) -> None:
    """
    Restore a Borg repository from S3.
    """
    if not offline:
        if not force and validator.repo_is_local(repo):
            raise ValueError("Repository already exists locally")

        status = "Performing dry run of S3 sync..." if dry_run else "Restoring repo from S3..."
        rich_utils.render_cmd_output_lines(
            status,
            "S3 sync completed successfully",
            s3.restore_from_s3(repo.safe_path, repo.name, dry_run),
            spinner="arrow",
            ruler_color=COLOR_HEX.blue,
        )
    else:
        console.print("Restoring a repository from S3 is not supported in offline mode.")


def restore_archive(repo_path: str, archive_name: str, offline: bool, passphrase: str | None = None) -> None:
    repo = lookup_repo(repo_path, None, offline)
    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    for log_msg in borg.extract(repo.path, archive_name, passphrase=resolved_passphrase):
        msg = validator.parse_log(log=log_msg)
        console.print(msg)


def delete_archive(
    repo_path: str, archive_name: str, dry_run: bool, offline: bool, passphrase: str | None = None
) -> None:
    repo = lookup_repo(repo_path, None, offline)
    if not validator.repo_is_local(repo):
        raise ValueError("Repository must be local to delete")
    if dry_run is False:
        rich_utils.confirm_deletion(repo.name, archive_name)

    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    rich_utils.render_cmd_output_lines(
        "Deleting archive",
        "Successfully deleted archive",
        borg.delete_archive(
            repo.path, repo.name, archive_name, dry_run, log_json=False, passphrase=resolved_passphrase
        ),
        spinner="pipe",
        ruler_color=COLOR_HEX.sapphire,
    )
    if not dry_run:
        # NOTE: Space is NOT reclaimed on disk until the 'compact' command is ran
        rich_utils.render_cmd_output_lines(
            "Compacting borg repo",
            "Compacting completed successfully",
            borg.compact(repo.path, log_json=False, passphrase=resolved_passphrase),
            spinner="dots",
            ruler_color=COLOR_HEX.mauve,
        )
        if not offline:
            # Refresh metadata after delete and compact complete
            repo.metadata = borg.info(repo.path, passphrase=resolved_passphrase)
            dynamodb.update_repo(repo)
        else:
            repo.metadata = borg.info(repo.path, passphrase=resolved_passphrase)
            offline_storage.store_borgboi_repo_metadata(repo)


def extract_repo_key(repo_path: str, offline: bool, passphrase: str | None = None) -> Path:
    repo = lookup_repo(repo_path, None, offline)
    resolved_passphrase = resolve_passphrase(
        repo_name=repo.name,
        cli_passphrase=passphrase,
        allow_env_fallback=True,
    )
    key_path = borg.export_repo_key(repo.path, repo.name, passphrase=resolved_passphrase)
    return key_path


def get_excludes_file(repo_name: str, offline: bool) -> Path:
    """
    Get the Path of the excludes file for a repository.

    Args:
        repo_name: Name of the repository

    Returns:
        Path: The pathlib Path of the excludes file

    Raises:
        FileNotFoundError: If the excludes file does not exist
        ValueError: If the repository is not local
    """
    # Validate repository is local
    repo = lookup_repo(None, repo_name, offline)
    if validator.repo_is_local(repo) is False:
        raise ValueError("Repository must be local to view excludes content")

    # Get the path to the exclude file
    excludes_path = _get_excludes_path(repo_name)

    # Check if the exclude file exists
    if not excludes_path.exists():
        raise FileNotFoundError(f"No exclude file found for repository {repo_name}")

    return excludes_path


def append_to_excludes_file(excludes_path: Path, new_content: str) -> None:
    """
    Append new content to the excludes file for a repository.

    Args:
        excludes_path: Path to the excludes file
        new_content: New line to be added to the excludes file
    """
    # Check if the excludes file exists
    if not excludes_path.exists():
        raise FileNotFoundError(f"No exclude file found at {excludes_path}")

    # Update the content of the excludes file
    with excludes_path.open("a") as f:
        f.write(new_content + "\n")
    console.print(f"Updated exclude list at [bold cyan]{excludes_path}[/]")

    # Count the total number of lines in the excludes file to use for highlighting
    with excludes_path.open("r") as f:
        line_count = sum(1 for _ in f)
    rich_utils.render_excludes_file(excludes_path.as_posix(), lines_to_highlight={line_count})


def remove_from_excludes_file(excludes_path: Path, line_number: int) -> None:
    """
    Remove a line from the excludes file for a repository.

    Args:
        excludes_path: Path to the excludes file
        line_number: Line number to be removed from the excludes file
    """
    # Check if the excludes file exists
    if not excludes_path.exists():
        raise FileNotFoundError(f"No exclude file found at {excludes_path}")
    # Read the content of the excludes file
    with excludes_path.open("r") as f:
        lines = f.readlines()
    if not validator.valid_line(lines, line_number):
        raise ValueError(f"Line number {line_number} is not valid")
    # Remove the specified line
    lines.pop(line_number - 1)
    # Write the updated content back to the excludes file
    with excludes_path.open("w") as f:
        f.writelines(lines)
    console.print(f"Removed line {line_number} from exclude list at [bold cyan]{excludes_path}[/]")
    rich_utils.render_excludes_file(excludes_path.as_posix())
