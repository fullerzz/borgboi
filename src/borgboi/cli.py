import click
from rich.traceback import install

from borgboi import orchestrator, rich_utils

install(suppress=[click])
console = rich_utils.console


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=False), prompt=True)
@click.option("--backup-target", "-b", required=True, type=click.Path(exists=True), prompt=True)
def create_repo(repo_path: str, backup_target: str) -> None:
    """Create a new Borg repository."""
    name = click.prompt("Enter a name for this repository")
    repo = orchestrator.create_borg_repo(path=repo_path, backup_path=backup_target, name=name)
    console.print(f"Created new Borg repo at [bold cyan]{repo.path}[/]")


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=False), prompt=True)
@click.option("--exclusions-source", "-x", required=True, type=click.Path(exists=True, dir_okay=False))
def create_exclusions(repo_path: str, exclusions_source: str) -> None:
    """Create a new exclusions list for a Borg repository."""
    repo = orchestrator.lookup_repo(repo_path, None)
    orchestrator.create_excludes_list(repo.name, exclusions_source)


@cli.command()
def list_repos() -> None:
    """List all BorgBoi repositories."""
    orchestrator.list_repos()


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=click.Path(exists=False))
def list_archives(repo_path: str | None, repo_name: str | None) -> None:
    """List the archives in a Borg repository."""
    orchestrator.list_archives(repo_path, repo_name)


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=click.Path(exists=False))
def get_repo(repo_path: str | None, repo_name: str | None) -> None:
    """Get a Borg repository by name or path."""
    repo = orchestrator.lookup_repo(repo_path, repo_name)
    console.print(f"Repository found: [bold cyan]{repo.path}[/]")
    console.print(repo)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
def daily_backup(repo_path: str) -> None:
    """Create a new archive of the repo's target directory with borg and perform pruning and compaction."""
    orchestrator.perform_daily_backup(repo_path)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
def export_repo_key(repo_path: str) -> None:
    """Extract the Borg repository's repo key."""
    key_path = orchestrator.extract_repo_key(repo_path)
    console.print(f"Exported repo key to: [bold cyan]{key_path}[/]")


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=click.Path(exists=False))
@click.option("--pp", is_flag=True, show_default=True, default=True, help="Pretty print the repo info")
def repo_info(repo_path: str | None, repo_name: str | None, pp: bool) -> None:
    """List a local Borg repository's info."""
    orchestrator.get_repo_info(repo_path, repo_name, pp)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
@click.option("--archive-name", "-a", required=True, prompt=True)
def extract_archive(repo_path: str, archive_name: str) -> None:
    """Extract a Borg archive into the current working directory."""
    click.confirm(
        "Confirm you want to extract the contents of this archive into the current working directory", abort=True
    )
    orchestrator.restore_archive(repo_path, archive_name)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
@click.option("--archive-name", "-a", required=True, prompt=True)
@click.option("--dry-run", is_flag=True, show_default=True, default=False, help="Perform a dry run of the deletion")
def delete_archive(repo_path: str, archive_name: str, dry_run: bool) -> None:
    """Delete a Borg archive from the repository."""
    orchestrator.delete_archive(repo_path, archive_name, dry_run)


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=click.Path(exists=False))
@click.option("--dry-run", is_flag=True, show_default=True, default=False, help="Perform a dry run of the deletion")
def delete_repo(repo_path: str | None, repo_name: str | None, dry_run: bool) -> None:
    """Delete a Borg repository."""
    orchestrator.delete_borg_repo(repo_path, repo_name, dry_run)


@cli.command()
@click.option("--repo-name", "-n", required=True, type=str, help="Name of the repository")
@click.option("--exclusion-pattern", "-x", required=True, type=str, help="Exclusion pattern to add")
def append_excludes(repo_name: str, exclusion_pattern: str) -> None:
    """Display the exclude patterns for a repository."""
    try:
        excludes_file = orchestrator.get_excludes_file(repo_name)
        orchestrator.append_to_excludes_file(excludes_file, exclusion_pattern)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
    except Exception as e:
        console.print(f"[bold red]Error:[/] An unexpected error occurred: {e}")


@cli.command()
@click.option("--repo-name", "-n", required=True, type=str, help="Name of the repository")
@click.option("--delete-line-num", "-D", required=True, type=int, help="Line number to delete")
def modify_excludes(repo_name: str, delete_line_num: int) -> None:
    """Delete a line from a repository's excludes file."""
    try:
        excludes_file = orchestrator.get_excludes_file(repo_name)
        orchestrator.remove_from_excludes_file(excludes_file, delete_line_num)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] {e}")
    except Exception as e:
        console.print(f"[bold red]Error:[/] An unexpected error occurred: {e}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
