"""Configuration management commands for BorgBoi CLI."""

import json
from pathlib import Path
from typing import Any

import click
import yaml
from rich.panel import Panel
from rich.syntax import Syntax

from borgboi.cli.main import BorgBoiContext, pass_context
from borgboi.config import Config, get_default_config_path, load_config_from_path
from borgboi.lib.colors import COLOR_HEX, PYGMENTS_STYLES
from borgboi.rich_utils import console


@click.group()
def config() -> None:
    """Configuration management commands.

    Display the effective BorgBoi configuration.
    """


def _config_to_dict(cfg: Config) -> dict[str, Any]:
    config_dict = cfg.model_dump(exclude_none=True, mode="json")
    borg_config = config_dict.get("borg")
    if isinstance(borg_config, dict) and "default_repo_path" in borg_config:
        borg_config["default_repo_path"] = str(borg_config["default_repo_path"])
    return config_dict


@config.command("show")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=False, dir_okay=False),
    help="Custom path for the configuration file to show (default: ~/.borgboi/config.yaml)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["yaml", "json"], case_sensitive=False),
    default="yaml",
    show_default=True,
    help="Output format when --no-pretty-print is set",
)
@click.option(
    "--pretty-print/--no-pretty-print",
    default=True,
    show_default=True,
    help="Pretty print output using rich",
)
@pass_context
def config_show(ctx: BorgBoiContext, path: str | None, output_format: str, pretty_print: bool) -> None:
    """Display the current BorgBoi configuration."""
    config_path = Path(path).expanduser() if path else get_default_config_path()

    try:
        if path:
            base_config = load_config_from_path(config_path)
            cfg = Config(
                aws=base_config.aws,
                borg=base_config.borg,
                ui=base_config.ui,
                offline=ctx.offline or base_config.offline,
                debug=ctx.debug or base_config.debug,
            )
        else:
            cfg = ctx.config
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1) from e

    config_dict = _config_to_dict(cfg)
    click.echo(f"Configuration from: {config_path}")
    click.echo("")

    normalized_format = output_format.lower()
    if pretty_print:
        if normalized_format == "json":
            output = json.dumps(config_dict, indent=2)
        else:
            output = yaml.safe_dump(config_dict, default_flow_style=False, sort_keys=False)

        syntax = Syntax(
            output,
            normalized_format,
            line_numbers=True,
            theme=PYGMENTS_STYLES["catppuccin-mocha"],
            padding=1,
        )
        panel = Panel(syntax, title="BorgBoi Config", border_style=COLOR_HEX.blue, expand=False)
        console.print(panel)
        return

    if normalized_format == "json":
        click.echo(json.dumps(config_dict, indent=2))
        return

    yaml_output = yaml.safe_dump(config_dict, default_flow_style=False, sort_keys=False)
    click.echo(yaml_output, nl=False)
