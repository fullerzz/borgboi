from pathlib import Path

import click
from rich.table import Table
from rich.traceback import install

from borgboi import backups, dynamodb, orchestrator, rich_utils

install(suppress=[click])
console = rich_utils.console


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=False), prompt=True)
def create_repo(repo_path: str) -> None:
    """Create a new Borg repository."""
    env_var_name = click.prompt("Enter the name of the environment variable that contains the passphrase for this repo")
    name = click.prompt("Enter a name for this repository")
    repo = orchestrator.create_borg_repo(path=repo_path, passphrase_env_var_name=env_var_name, name=name)
    console.print(f"Created new Borg repo at [bold cyan]{repo.path.as_posix()}[/]")


@cli.command()
def list_repos() -> None:
    """Create a new Borg repository."""
    repos = dynamodb.get_all_repos()
    table = Table(title="BorgBoi Repositories")
    table.add_column("Name")
    table.add_column("Local Path")
    table.add_column("Passphrase Environment Variable")
    for repo in repos:
        table.add_row(repo.name, repo.path.as_posix(), repo.passphrase_env_var_name)
    console.print(table)


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
def create_archive() -> None:
    """Create a new archive of the home directory with borg."""
    console.rule("Preparing to perform daily backup")
    # TODO: Add ability to query dynamo and retrieve repo info in order to remove hardcoded name
    repo = backups.BorgRepo(path=Path("/opt/borg-repos/home"), name="home")
    dir_to_backup = Path.home()
    console.print(
        f"Creating new archive of [bold cyan]{dir_to_backup.as_posix()}[/] inside the borg repo at [bold cyan]{repo.path.as_posix()}[/]"
    )
    repo.create_archive(dir_to_backup=dir_to_backup)
    console.print(":heavy_check_mark: [bold green]Backup completed successfully[/]")


@cli.command()
def prune() -> None:
    """Prune old backups from the borg repo."""
    console.rule("Pruning old backups")
    # TODO: Add ability to query dynamo and retrieve repo info in order to remove hardcoded name
    repo = backups.BorgRepo(path=Path("/opt/borg-repos/home"), name="home")
    console.print(f"Pruning old backups in the borg repo at [bold cyan]{repo.path.as_posix()}[/]")
    repo.prune()
    console.print(":heavy_check_mark: [bold green]Pruning completed successfully[/]")


@cli.command()
def compact() -> None:
    """Compact the borg repo."""
    console.rule("Compacting the borg repo")
    # TODO: Add ability to query dynamo and retrieve repo info in order to remove hardcoded name
    repo = backups.BorgRepo(path=Path("/opt/borg-repos/home"), name="home")
    console.print(f"Compacting the borg repo at [bold cyan]{repo.path.as_posix()}[/]")
    repo.compact()
    console.print(":heavy_check_mark: [bold green]Compaction completed successfully[/]")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
