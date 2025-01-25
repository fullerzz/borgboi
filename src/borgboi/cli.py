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
    env_var_name = click.prompt("Enter the name of the environment variable that contains the passphrase for this repo")
    name = click.prompt("Enter a name for this repository")
    repo = orchestrator.create_borg_repo(
        path=repo_path, backup_path=backup_target, passphrase_env_var_name=env_var_name, name=name
    )
    console.print(f"Created new Borg repo at [bold cyan]{repo.path.as_posix()}[/]")


@cli.command()
def list_repos() -> None:
    """Create a new Borg repository."""
    orchestrator.list_repos()


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=click.Path(exists=False))
def get_repo(repo_path: str | None, repo_name: str | None) -> None:
    """Get a Borg repository by name or path."""
    repo = orchestrator.lookup_repo(repo_path, repo_name)
    console.print(f"Repository found: [bold cyan]{repo.path.as_posix()}[/]")
    console.print(repo)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
def daily_backup(repo_path: str) -> None:
    """Create a new archive of the home directory with borg and perform pruning and compaction."""
    orchestrator.perform_daily_backup(repo_path)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
def export_repo_key(repo_path: str) -> None:
    """Create a new archive of the home directory with borg and perform pruning and compaction."""
    repo = orchestrator.lookup_repo(repo_path, None)
    repo.export_repo_key()


@cli.command()
@click.option("--repo-path", "-r", required=False, type=click.Path(exists=False))
@click.option("--repo-name", "-n", required=False, type=click.Path(exists=False))
def repo_info(repo_path: str | None, repo_name: str | None) -> None:
    """List a local Borg repository's info."""
    orchestrator.get_repo_info(repo_path, repo_name)


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
@click.option("--archive-name", "-a", required=True, prompt=True)
def extract_archive(repo_path: str, archive_name: str) -> None:
    """Extract a Borg archive into the current working directory."""
    click.confirm(
        "Confirm you want to extract the contents of this archive into the current working directory", abort=True
    )
    orchestrator.restore_archive(repo_path, archive_name)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
