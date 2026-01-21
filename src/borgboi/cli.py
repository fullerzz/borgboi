import click
from rich.traceback import install

from borgboi import orchestrator, rich_utils
from borgboi.config import config

install(suppress=[click])
console = rich_utils.console


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=False), prompt=True)
@click.option("--backup-target", "-b", required=True, type=click.Path(exists=True), prompt=True)
@click.option(
    "--passphrase", "-p", type=str, default=None, help="Passphrase for new repository (falls back to env var or config)"
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def create_repo(repo_path: str, backup_target: str, passphrase: str | None, offline: bool) -> None:
    """Create a new Borg repository."""
    name = click.prompt("Enter a name for this repository")
    repo = orchestrator.create_borg_repo(
        path=repo_path, backup_path=backup_target, name=name, offline=offline, passphrase=passphrase
    )
    console.print(f"Created new Borg repo at [bold cyan]{repo.path}[/]")


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=False), prompt=True)
@click.option("--exclusions-source", "-x", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def create_exclusions(repo_path: str, exclusions_source: str, offline: bool) -> None:
    """Create a new exclusions list for a Borg repository."""
    repo = orchestrator.lookup_repo(repo_path, None, offline)
    orchestrator.create_excludes_list(repo.name, exclusions_source)


@cli.command()
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def list_repos(offline: bool) -> None:
    """List all BorgBoi repositories."""
    orchestrator.list_repos(offline)


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=str)
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def list_archives(repo_path: str | None, repo_name: str | None, passphrase: str | None, offline: bool) -> None:
    """List the archives in a Borg repository."""
    orchestrator.list_archives(repo_path, repo_name, offline, passphrase=passphrase)


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=str)
@click.option("--archive-name", "-a", required=True, type=str)
@click.option("--output", "-o", required=False, type=str, default="stdout", help="Output file path or stdout")
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def list_archive_contents(
    repo_path: str | None, repo_name: str | None, archive_name: str, output: str, passphrase: str | None, offline: bool
) -> None:
    """List the contents of a Borg archive."""
    orchestrator.list_archive_contents(repo_path, repo_name, archive_name, output, offline, passphrase=passphrase)


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=str)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def get_repo(repo_path: str | None, repo_name: str | None, offline: bool) -> None:
    """Get a Borg repository by name or path."""
    repo = orchestrator.lookup_repo(repo_path, repo_name, offline)
    console.print(f"Repository found: [bold cyan]{repo.path}[/]")
    console.print(repo)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def daily_backup(repo_path: str, passphrase: str | None, offline: bool) -> None:
    """Create a new archive of the repo's target directory with borg and perform pruning and compaction."""
    orchestrator.perform_daily_backup(repo_path, offline, passphrase=passphrase)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def export_repo_key(repo_path: str, passphrase: str | None, offline: bool) -> None:
    """Extract the Borg repository's repo key."""
    key_path = orchestrator.extract_repo_key(repo_path, offline, passphrase=passphrase)
    console.print(f"Exported repo key to: [bold cyan]{key_path}[/]")


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=str)
@click.option("--pp", is_flag=True, show_default=True, default=True, help="Pretty print the repo info")
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def repo_info(repo_path: str | None, repo_name: str | None, pp: bool, passphrase: str | None, offline: bool) -> None:
    """List a local Borg repository's info."""
    orchestrator.get_repo_info(repo_path, repo_name, pp, offline, passphrase=passphrase)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
@click.option("--archive-name", "-a", required=True, prompt=True)
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def extract_archive(repo_path: str, archive_name: str, passphrase: str | None, offline: bool) -> None:
    """Extract a Borg archive into the current working directory."""
    click.confirm(
        "Confirm you want to extract the contents of this archive into the current working directory", abort=True
    )
    orchestrator.restore_archive(repo_path, archive_name, offline, passphrase=passphrase)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
@click.option("--archive-name", "-a", required=True, prompt=True)
@click.option("--dry-run", is_flag=True, show_default=True, default=False, help="Perform a dry run of the deletion")
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def delete_archive(repo_path: str, archive_name: str, dry_run: bool, passphrase: str | None, offline: bool) -> None:
    """Delete a Borg archive from the repository."""
    orchestrator.delete_archive(repo_path, archive_name, dry_run, offline, passphrase=passphrase)


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=str)
@click.option("--dry-run", is_flag=True, show_default=True, default=False, help="Perform a dry run of the deletion")
@click.option(
    "--passphrase",
    "-p",
    type=str,
    default=None,
    help="Passphrase override (uses stored passphrase, env var, or config if not provided)",
)
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def delete_repo(
    repo_path: str | None, repo_name: str | None, dry_run: bool, passphrase: str | None, offline: bool
) -> None:
    """Delete a Borg repository."""
    orchestrator.delete_borg_repo(repo_path, repo_name, dry_run, offline, passphrase=passphrase)


@cli.command()
@click.option("--repo-name", "-n", required=True, type=str, help="Name of the repository")
@click.option("--exclusion-pattern", "-x", required=True, type=str, help="Exclusion pattern to add")
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def append_excludes(repo_name: str, exclusion_pattern: str, offline: bool) -> None:
    """Append new exclusion pattern to the excludes file for a repository."""
    try:
        excludes_file = orchestrator.get_excludes_file(repo_name, offline)
        orchestrator.append_to_excludes_file(excludes_file, exclusion_pattern)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
    except Exception as e:
        console.print(f"[bold red]Error:[/] An unexpected error occurred: {e}")


@cli.command()
@click.option("--repo-name", "-n", required=True, type=str, help="Name of the repository")
@click.option("--delete-line-num", "-D", required=True, type=int, help="Line number to delete")
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def modify_excludes(repo_name: str, delete_line_num: int, offline: bool) -> None:
    """Delete a line from a repository's excludes file."""
    try:
        excludes_file = orchestrator.get_excludes_file(repo_name, offline)
        orchestrator.remove_from_excludes_file(excludes_file, delete_line_num)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
    except Exception as e:
        console.print(f"[bold red]Error:[/] An unexpected error occurred: {e}")


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=str)
@click.option("--dry-run", is_flag=True, show_default=True, default=False, help="Perform a dry run of the restore")
@click.option("--force", is_flag=True, show_default=True, default=False, help="Force restore even if repo exists")
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def restore_repo(repo_path: str | None, repo_name: str | None, dry_run: bool, force: bool, offline: bool) -> None:
    """Restore a Borg repository by name or path by downloading it from S3."""
    repo = orchestrator.lookup_repo(repo_path, repo_name, offline)
    if repo.metadata and repo.metadata.cache:
        console.print(
            f"Repository found: [bold cyan]{repo.path} - Total size: {repo.metadata.cache.total_size_gb} GB[/]"
        )
    else:
        console.print(f"Repository found: [bold cyan]{repo.path}[/]")
    orchestrator.restore_repo(repo, dry_run, force, offline)


@cli.command()
@click.option("--repo-name", "-n", type=str, help="Specific repo to migrate (migrates all if omitted)")
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, default=config.offline)
def migrate_passphrases(repo_name: str | None, offline: bool) -> None:
    """Migrate repository passphrases from database to secure file storage.

    This command migrates passphrases stored in the database to individual
    files at ~/.borgboi/passphrases/{repo-name}.key with 0o600 permissions.

    Examples:
        # Migrate a specific repository
        bb migrate-passphrases --repo-name my-repo

        # Migrate all repositories
        bb migrate-passphrases
    """
    if repo_name:
        # Migrate specific repo
        try:
            repo = orchestrator.lookup_repo(None, repo_name, offline)
            orchestrator.migrate_repo_passphrase_to_file(repo, offline)
        except Exception as e:
            console.print(f"[bold red]Failed to migrate {repo_name}: {e}[/]")
    else:
        # Migrate all repos
        try:
            repos = orchestrator.list_repos_data(offline)
            migrated = 0
            already_migrated = 0
            failed = 0
            skipped = 0

            console.print("\n[bold]Starting passphrase migration...[/]\n")

            for repo in repos:
                try:
                    if repo.passphrase_migrated:
                        console.print(f"[dim]✓ {repo.name} (already migrated)[/]")
                        already_migrated += 1
                        continue
                    if repo.passphrase is None:
                        console.print(f"[yellow]⊘ {repo.name} (no passphrase to migrate)[/]")
                        skipped += 1
                        continue
                    orchestrator.migrate_repo_passphrase_to_file(repo, offline)
                    migrated += 1
                except Exception as e:
                    console.print(f"[bold red]✗ Failed to migrate {repo.name}: {e}[/]")
                    failed += 1

            console.print("\n[bold]Migration Summary:[/]")
            console.print(f"  [green]Migrated:[/] {migrated}")
            console.print(f"  [dim]Already migrated:[/] {already_migrated}")
            console.print(f"  [yellow]Skipped (no passphrase):[/] {skipped}")
            if failed > 0:
                console.print(f"  [red]Failed:[/] {failed}")
        except Exception as e:
            console.print(f"[bold red]Migration failed: {e}[/]")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
