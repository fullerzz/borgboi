"""Configuration management commands for BorgBoi CLI."""

import json
from pathlib import Path
from typing import Any

import click
import yaml
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree

from borgboi.cli.main import BorgBoiContext, pass_context
from borgboi.config import Config, get_default_config_path, get_env_overrides, load_config_from_path
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


def _format_value(value: Any) -> str:
    """Format a value for display in the config tree."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return value
    return str(value)


def _add_dict_to_tree(
    tree: Tree,
    data: dict[str, Any],
    env_overrides: dict[str, str],
    path_prefix: str = "",
) -> None:
    """Recursively add dictionary items to a tree with env override highlighting.

    Args:
        tree: The Rich Tree to add items to.
        data: The dictionary data to render.
        env_overrides: Dict mapping config paths to env var names for overridden values.
        path_prefix: Current path prefix for nested keys (e.g., "aws." for aws.s3_bucket).
    """
    for key, value in data.items():
        full_path = f"{path_prefix}{key}" if path_prefix else key

        if isinstance(value, dict):
            # Create a branch for nested dictionaries
            branch = tree.add(f"[bold {COLOR_HEX.blue}]{key}[/]")
            _add_dict_to_tree(branch, value, env_overrides, f"{full_path}.")
        else:
            # Leaf value - check if it's an env override
            formatted_value = _format_value(value)
            if full_path in env_overrides:
                env_var = env_overrides[full_path]
                # Use yellow/peach color to indicate env var override
                text = Text()
                text.append(f"{key}: ", style=f"bold {COLOR_HEX.text}")
                text.append(formatted_value, style=f"bold {COLOR_HEX.yellow}")
                text.append(f" (from {env_var})", style=f"italic {COLOR_HEX.peach}")
                tree.add(text)
            else:
                tree.add(f"[{COLOR_HEX.text}]{key}:[/] [{COLOR_HEX.green}]{formatted_value}[/]")


def _render_config_with_env_highlights(
    config_dict: dict[str, Any],
    env_overrides: dict[str, str],
) -> Tree:
    """Render config as a Rich Tree with env overrides highlighted.

    Args:
        config_dict: The configuration dictionary to render.
        env_overrides: Dict mapping config paths to env var names for overridden values.

    Returns:
        A Rich Tree object ready for display.
    """
    tree = Tree(f"[bold {COLOR_HEX.mauve}]BorgBoi Config[/]")
    _add_dict_to_tree(tree, config_dict, env_overrides)
    return tree


def _render_tree_panel(config_dict: dict[str, Any], env_overrides: dict[str, str]) -> None:
    """Render config as a tree panel with env override highlighting."""
    tree = _render_config_with_env_highlights(config_dict, env_overrides)
    panel = Panel(tree, border_style=COLOR_HEX.blue, expand=False)
    console.print(panel)
    if env_overrides:
        console.print(
            f"\n[{COLOR_HEX.yellow}]Yellow values[/] indicate environment variable overrides.",
            highlight=False,
        )


def _render_syntax_panel(config_dict: dict[str, Any], output_format: str) -> None:
    """Render config as a syntax-highlighted panel."""
    if output_format == "json":
        output = json.dumps(config_dict, indent=2)
    else:
        output = yaml.safe_dump(config_dict, default_flow_style=False, sort_keys=False)

    syntax = Syntax(
        output,
        output_format,
        line_numbers=True,
        theme=PYGMENTS_STYLES["catppuccin-mocha"],  # type: ignore[arg-type]
        padding=1,
    )
    panel = Panel(syntax, title="BorgBoi Config", border_style=COLOR_HEX.blue, expand=False)
    console.print(panel)


def _render_plain_text(config_dict: dict[str, Any], output_format: str, env_overrides: dict[str, str]) -> None:
    """Render config as plain text with optional env override notes."""
    if output_format == "json":
        click.echo(json.dumps(config_dict, indent=2))
        return

    yaml_output = yaml.safe_dump(config_dict, default_flow_style=False, sort_keys=False)
    click.echo(yaml_output, nl=False)

    if env_overrides:
        click.echo("")
        click.echo("# Values from environment variables:")
        for config_path_key, env_var in sorted(env_overrides.items()):
            click.echo(f"#   {config_path_key} <- {env_var}")


def _load_config_for_show(ctx: BorgBoiContext, path: str | None, config_path: Path) -> Config:
    """Load configuration for the show command."""
    if path:
        base_config = load_config_from_path(config_path)
        return Config(
            aws=base_config.aws,
            borg=base_config.borg,
            ui=base_config.ui,
            offline=ctx.offline or base_config.offline,
            debug=ctx.debug or base_config.debug,
        )
    return ctx.config


def _get_source_message(path: str | None, config_path: Path) -> str:
    """Generate the configuration source message."""
    if path:
        return f"Configuration from: {config_path}"
    if config_path.exists():
        return f"Configuration from: {config_path}"
    return f"Configuration from: {config_path} (file not found, using defaults)"


@config.command("show")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=False, dir_okay=False),
    help="Custom path for the configuration file to show (default: ~/.borgboi/borgboi.db)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["yaml", "json", "tree"], case_sensitive=False),
    default="yaml",
    show_default=True,
    help="Output format: yaml/json for text output, tree for Rich tree with env override highlighting",
)
@click.option(
    "--pretty-print/--no-pretty-print",
    default=True,
    show_default=True,
    help="Pretty print output using rich (only applies to yaml/json formats)",
)
@pass_context
def config_show(ctx: BorgBoiContext, path: str | None, output_format: str, pretty_print: bool) -> None:
    """Display the current BorgBoi configuration.

    Values overridden by environment variables are highlighted in yellow when using
    the tree format (--format tree) or pretty-print mode (default) for YAML output.
    JSON output includes an "_env_overrides" mapping when overrides are present.
    """
    config_path = Path(path).expanduser() if path else get_default_config_path()

    try:
        cfg = _load_config_for_show(ctx, path, config_path)
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
    env_overrides = get_env_overrides()

    click.echo(_get_source_message(path, config_path))
    click.echo("")

    normalized_format = output_format.lower()

    if normalized_format == "json" and env_overrides:
        output_config_dict = dict(config_dict)
        output_config_dict["_env_overrides"] = env_overrides
    else:
        output_config_dict = config_dict

    # Tree format or pretty-print with env overrides: use rich tree
    if normalized_format == "tree" or (pretty_print and env_overrides and normalized_format != "json"):
        _render_tree_panel(config_dict, env_overrides)
        return

    # Pretty-print without env overrides: use syntax highlighting
    if pretty_print:
        _render_syntax_panel(output_config_dict, normalized_format)
        return

    # Plain text output
    _render_plain_text(output_config_dict, normalized_format, env_overrides)
