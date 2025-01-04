import click
from rich.traceback import install

install()


@click.group()
def cli() -> None:
    pass


@cli.command()
def test() -> None:
    click.echo("Test command executing")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
