"""Main CLI group for BorgBoi.

This module provides the top-level CLI group and common options.
"""

from typing import Any

import click
from rich.traceback import install

from borgboi.config import Config, get_config
from borgboi.core.orchestrator import Orchestrator

# Install rich traceback handler
install(suppress=[click])


class BorgBoiContext:
    """Context object passed to all CLI commands.

    Attributes:
        orchestrator: The main orchestrator instance
        config: Current configuration
        offline: Whether running in offline mode
        debug: Whether debug mode is enabled
    """

    def __init__(self, offline: bool = False, debug: bool = False) -> None:
        self.offline = offline
        self.debug = debug
        self._orchestrator: Orchestrator | None = None
        self._config: Config | None = None

    @property
    def orchestrator(self) -> Orchestrator:
        """Get or create the orchestrator instance."""
        if self._orchestrator is None:
            self._orchestrator = Orchestrator(config=self.config)
        return self._orchestrator

    @property
    def config(self) -> Config:
        """Get or create the config instance."""
        if self._config is None:
            base_config = get_config()
            # Override with CLI options
            self._config = Config(
                aws=base_config.aws,
                borg=base_config.borg,
                ui=base_config.ui,
                offline=self.offline or base_config.offline,
                debug=self.debug or base_config.debug,
            )
        return self._config


pass_context: Any = click.make_pass_decorator(BorgBoiContext)


@click.group()
@click.option("--offline", envvar="BORGBOI_OFFLINE", is_flag=True, help="Run in offline mode (no AWS)")
@click.option("--debug", envvar="BORGBOI_DEBUG", is_flag=True, help="Enable debug output")
@click.version_option()
@click.pass_context
def cli(ctx: click.Context, offline: bool, debug: bool) -> None:
    """BorgBoi - Borg backup automation with AWS integration.

    Use subcommands to manage repositories and backups:

    \b
      repo       - Repository management (create, list, info, delete)
      backup     - Backup operations (run, daily, list, restore, delete)
      s3         - S3 sync operations (sync, restore, delete)
      exclusions - Manage backup exclusions
      config     - Show configuration values

    For backward compatibility, legacy commands (create-repo, daily-backup, etc.)
    are still available as top-level commands.
    """
    ctx.obj = BorgBoiContext(offline=offline, debug=debug)


def _register_commands() -> None:
    """Import and register subcommands after cli definition to avoid circular imports."""
    from borgboi.cli.backup import backup
    from borgboi.cli.config import config
    from borgboi.cli.exclusions import exclusions
    from borgboi.cli.legacy import register_legacy_commands
    from borgboi.cli.repo import repo
    from borgboi.cli.s3 import s3

    cli.add_command(repo)
    cli.add_command(backup)
    cli.add_command(s3)
    cli.add_command(exclusions)
    cli.add_command(config)
    register_legacy_commands(cli)


_register_commands()


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
