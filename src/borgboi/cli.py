from os import environ
from pathlib import Path
import click
from rich.traceback import install


from borgboi import backups, rich_utils

install()
console = rich_utils.get_console()


@click.group()
def cli() -> None:
    pass


@cli.command()
def test() -> None:
    click.echo("Test command executing")


@cli.command()
def daily_backup() -> None:
    """Create a new archive of the home directory with borg."""
    console.rule("Preparing to perform daily backup")
    repo = backups.BorgRepo(
        path=Path("/opt/borg-repos/home"),
        passphrase=environ["BORG_PASSPHRASE"],  # type: ignore
    )
    dir_to_backup = Path.home()
    console.log(
        f"Creating new archive of [bold cyan]{dir_to_backup.as_posix()}[/] inside the borg repo at [bold cyan]{repo.path.as_posix()}[/]"
    )
    backups.create_archive(repo=repo, dir_to_backup=dir_to_backup)
    console.log(":heavy_check_mark: [bold green]Backup completed successfully[/]")


@cli.command()
def prune() -> None:
    """Prune old backups from the borg repo."""
    console.rule("Pruning old backups")
    repo = backups.BorgRepo(
        path=Path("/opt/borg-repos/home"),
        passphrase=environ["BORG_PASSPHRASE"],  # type: ignore
    )
    console.log(
        f"Pruning old backups in the borg repo at [bold cyan]{repo.path.as_posix()}[/]"
    )
    backups.prune(repo=repo)
    console.log(":heavy_check_mark: [bold green]Pruning completed successfully[/]")


@cli.command()
def compact() -> None:
    """Compact the borg repo."""
    console.rule("Compacting the borg repo")
    repo = backups.BorgRepo(
        path=Path("/opt/borg-repos/home"),
        passphrase=environ["BORG_PASSPHRASE"],  # type: ignore
    )
    console.log(f"Compacting the borg repo at [bold cyan]{repo.path.as_posix()}[/]")
    backups.compact(repo=repo)
    console.log(":heavy_check_mark: [bold green]Compaction completed successfully[/]")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
