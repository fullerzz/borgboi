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
    if isinstance(borg_config, dict):
        # Normalize path fields for display
        if "default_repo_path" in borg_config:
            borg_config["default_repo_path"] = str(borg_config["default_repo_path"])
        # Redact sensitive fields to avoid exposing secrets in output
        for sensitive_key in ("borg_passphrase", "borg_new_passphrase"):
            if sensitive_key in borg_config and borg_config[sensitive_key] is not None:
                borg_config[sensitive_key] = "***REDACTED***"
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
    help="Output format for configuration (affects syntax highlighting when pretty-print is enabled)",
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
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/] Configuration file not found: {config_path}")
        raise SystemExit(1) from e
    except PermissionError as e:
        console.print(f"[bold red]Error:[/] Permission denied when reading configuration file: {config_path}")
        raise SystemExit(1) from e
    except yaml.YAMLError as e:
        console.print(f"[bold red]Error:[/] Invalid YAML configuration in {config_path}: {e}")
        raise SystemExit(1) from e
    except Exception as e:
        console.print(f"[bold red]Error:[/] Unexpected error while loading configuration: {e}")
        raise SystemExit(1) from e

    config_dict = _config_to_dict(cfg)
    if path:
        source_message = f"Configuration from: {config_path}"
    else:
        if config_path.exists():
            source_message = f"Configuration from: {config_path}"
        else:
            source_message = f"Configuration from: {config_path} (file not found, using defaults)"
    click.echo(source_message)
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
