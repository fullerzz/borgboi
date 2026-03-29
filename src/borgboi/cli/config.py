"""Configuration management commands for BorgBoi CLI."""

import json
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from cyclopts import App, Parameter
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree

from borgboi.cli.main import BorgBoiContext, ContextArg, print_error_and_exit
from borgboi.config import Config, get_default_config_path, get_env_overrides, load_config_from_path
from borgboi.core.logging import get_logger
from borgboi.lib.colors import COLOR_HEX, PYGMENTS_STYLES
from borgboi.rich_utils import console

logger = get_logger(__name__)

config = App(
    name="config",
    help="Configuration management commands.\n\nDisplay the effective BorgBoi configuration.",
)


def _write_stdout(text: str) -> None:
    console.file.write(text)
    console.file.flush()


def _config_to_dict(cfg: Config) -> dict[str, Any]:
    config_dict = cfg.model_dump(exclude_none=True, mode="json")
    borg_config = config_dict.get("borg")
    if isinstance(borg_config, dict):
        if "default_repo_path" in borg_config:
            borg_config["default_repo_path"] = str(borg_config["default_repo_path"])
        for sensitive_key in ("borg_passphrase", "borg_new_passphrase"):
            if sensitive_key in borg_config and borg_config[sensitive_key] is not None:
                borg_config[sensitive_key] = "***REDACTED***"
    return config_dict


def _format_value(value: Any) -> str:
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
    for key, value in data.items():
        full_path = f"{path_prefix}{key}" if path_prefix else key

        if isinstance(value, dict):
            branch = tree.add(f"[bold {COLOR_HEX.blue}]{key}[/]")
            _add_dict_to_tree(branch, value, env_overrides, f"{full_path}.")
            continue

        formatted_value = _format_value(value)
        if full_path in env_overrides:
            env_var = env_overrides[full_path]
            text = Text()
            text.append(f"{key}: ", style=f"bold {COLOR_HEX.text}")
            text.append(formatted_value, style=f"bold {COLOR_HEX.yellow}")
            text.append(f" (from {env_var})", style=f"italic {COLOR_HEX.peach}")
            tree.add(text)
            continue

        tree.add(f"[{COLOR_HEX.text}]{key}:[/] [{COLOR_HEX.green}]{formatted_value}[/]")


def _render_config_with_env_highlights(config_dict: dict[str, Any], env_overrides: dict[str, str]) -> Tree:
    tree = Tree(f"[bold {COLOR_HEX.mauve}]BorgBoi Config[/]")
    _add_dict_to_tree(tree, config_dict, env_overrides)
    return tree


def _render_tree_panel(config_dict: dict[str, Any], env_overrides: dict[str, str]) -> None:
    tree = _render_config_with_env_highlights(config_dict, env_overrides)
    panel = Panel(tree, border_style=COLOR_HEX.blue, expand=False)
    console.print(panel)
    if env_overrides:
        console.print(
            f"\n[{COLOR_HEX.yellow}]Yellow values[/] indicate environment variable overrides.",
            highlight=False,
        )


def _render_syntax_panel(config_dict: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        output = json.dumps(config_dict, indent=2)
    else:
        output = yaml.safe_dump(config_dict, default_flow_style=False, sort_keys=False)

    syntax = Syntax(
        output,
        output_format,
        line_numbers=True,
        theme=PYGMENTS_STYLES["catppuccin-mocha"],
        padding=1,
    )
    panel = Panel(syntax, title="BorgBoi Config", border_style=COLOR_HEX.blue, expand=False)
    console.print(panel)


def _render_plain_text(config_dict: dict[str, Any], output_format: str, env_overrides: dict[str, str]) -> None:
    if output_format == "json":
        _write_stdout(json.dumps(config_dict, indent=2) + "\n")
        return

    yaml_output = yaml.safe_dump(config_dict, default_flow_style=False, sort_keys=False)
    _write_stdout(yaml_output)

    if env_overrides:
        _write_stdout("\n")
        _write_stdout("# Values from environment variables:\n")
        for config_path_key, env_var in sorted(env_overrides.items()):
            _write_stdout(f"#   {config_path_key} <- {env_var}\n")


def _load_config_for_show(ctx: BorgBoiContext, path: str | None, config_path: Path) -> Config:
    if path:
        logger.debug("Loading configuration from custom path", config_path=str(config_path))
        base_config = load_config_from_path(config_path)
        return base_config.model_copy(
            update={
                "offline": ctx.offline or base_config.offline,
                "debug": ctx.debug or base_config.debug,
            }
        )
    logger.debug("Using context configuration for config show", offline=ctx.offline, debug=ctx.debug)
    return ctx.config


def _get_source_message(path: str | None, config_path: Path) -> str:
    if path or config_path.exists():
        return f"Configuration from: {config_path}"
    return f"Configuration from: {config_path} (file not found, using defaults)"


@config.command(name="show")
def config_show(
    *,
    path: Annotated[
        str | None,
        Parameter(
            name=["--path", "-p"],
            help="Custom path for the configuration file to show (default: ~/.borgboi/config.yaml)",
        ),
    ] = None,
    output_format: Annotated[
        Literal["yaml", "json", "tree"],
        Parameter(
            name=["--format", "-f"],
            help="Output format: yaml/json for text output, tree for Rich tree with env override highlighting",
        ),
    ] = "yaml",
    pretty_print: Annotated[
        bool,
        Parameter(
            name="--pretty-print",
            negative="--no-pretty-print",
            help="Pretty print output using rich (only applies to yaml/json formats)",
        ),
    ] = True,
    ctx: ContextArg,
) -> None:
    """Display the current BorgBoi configuration."""
    config_path = Path(path).expanduser() if path else get_default_config_path()
    cfg: Config | None = None

    logger.info(
        "Running config show command",
        config_path=str(config_path),
        has_custom_path=path is not None,
        output_format=output_format,
        pretty_print=pretty_print,
    )

    try:
        cfg = _load_config_for_show(ctx, path, config_path)
    except FileNotFoundError as error:
        logger.exception(
            "Config show command failed to find configuration file", config_path=str(config_path), error=str(error)
        )
        print_error_and_exit(f"Configuration file not found: {config_path}", error=error)
    except PermissionError as error:
        logger.exception(
            "Config show command failed due to permission error",
            config_path=str(config_path),
            error=str(error),
        )
        print_error_and_exit(f"Permission denied when reading configuration file: {config_path}", error=error)
    except yaml.YAMLError as error:
        logger.exception(
            "Config show command failed due to invalid YAML", config_path=str(config_path), error=str(error)
        )
        print_error_and_exit(f"Invalid YAML configuration in {config_path}: {error}", error=error)
    except Exception as error:
        logger.exception("Config show command failed unexpectedly", config_path=str(config_path), error=str(error))
        print_error_and_exit(f"Unexpected error while loading configuration: {error}", error=error)

    assert cfg is not None

    config_dict = _config_to_dict(cfg)
    env_overrides = get_env_overrides()
    logger.debug(
        "Prepared configuration output",
        config_path=str(config_path),
        output_format=output_format,
        pretty_print=pretty_print,
        env_override_count=len(env_overrides),
    )

    _write_stdout(_get_source_message(path, config_path) + "\n\n")

    if output_format == "json" and env_overrides:
        output_config_dict = {**config_dict, "_env_overrides": env_overrides}
    else:
        output_config_dict = config_dict

    if output_format == "tree" or (pretty_print and env_overrides and output_format != "json"):
        logger.debug(
            "Rendering configuration as tree",
            config_path=str(config_path),
            env_override_count=len(env_overrides),
        )
        _render_tree_panel(config_dict, env_overrides)
        return

    if pretty_print:
        logger.debug(
            "Rendering configuration with syntax highlighting",
            config_path=str(config_path),
            output_format=output_format,
        )
        _render_syntax_panel(output_config_dict, output_format)
        return

    logger.debug("Rendering configuration as plain text", config_path=str(config_path), output_format=output_format)
    _render_plain_text(output_config_dict, output_format, env_overrides)
