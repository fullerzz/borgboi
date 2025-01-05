from os import environ
from pathlib import Path
import click
from rich.traceback import install


from borgboi import backups, rich_utils, s3_sync

install()
console = rich_utils.get_console()


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--repo-path", "-r", required=True, type=click.Path(exists=True))
def daily_backup(repo_path: str) -> None:
    """Create a new archive of the home directory with borg and perform pruning and compaction."""
    console.rule("Preparing to perform backup")
    repo = backups.BorgRepo(
        path=Path(repo_path),
        passphrase=environ["BORG_PASSPHRASE"],  # type: ignore
    )
    dir_to_backup = Path.home()
    console.log(
        f"Creating new archive of [bold cyan]{dir_to_backup.as_posix()}[/] inside the borg repo at [bold cyan]{repo.path.as_posix()}[/]"
    )
    repo.create_archive(dir_to_backup=dir_to_backup)
    console.log(":heavy_check_mark: [bold green]Backup completed successfully[/]")
    console.rule("Pruning old backups and compacting the repo")
    repo.prune()
    repo.compact()
    console.log(
        ":heavy_check_mark: [bold green]Pruning and compaction completed successfully[/]"
    )
    s3_sync.sync_repo(repo)


@cli.command()
def create_archive() -> None:
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
    repo.create_archive(dir_to_backup=dir_to_backup)
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
    repo.prune()
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
    repo.compact()
    console.log(":heavy_check_mark: [bold green]Compaction completed successfully[/]")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
