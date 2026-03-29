"""Config display panel for the BorgBoi TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Static

from borgboi.core.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from borgboi.config import Config


def _render_value(value: str | bool) -> str:
    """Render a config value as Rich markup."""
    if isinstance(value, bool):
        if value:
            return "[#a6e3a1]True[/]"
        return "[#f38ba8]False[/]"
    return f"[#cdd6f4]{escape(value)}[/]"


def _aws_profile_display(profile: str | None) -> str:
    """Render the configured AWS profile without implying one is active."""
    return profile or "provider chain"


def _render_section(fields: dict[str, str | bool]) -> str:
    """Format key-value pairs as Rich markup lines."""
    lines: list[str] = []
    for label, value in fields.items():
        lines.append(f"[#89b4fa]{escape(label)}:[/] {_render_value(value)}")
    return "\n".join(lines)


class ConfigPanel(VerticalScroll):
    """Sidebar panel displaying the current borgboi configuration."""

    DEFAULT_CSS = ""

    def __init__(self, config: Config | None = None, **kwargs: Any) -> None:
        super().__init__(id="config-panel", **kwargs)
        self._config = config

    @override
    def compose(self) -> ComposeResult:
        """Build the config panel with collapsible sections for each config group."""
        yield Static(
            "[bold #cba6f7]Configuration[/]",
            id="config-panel-title",
            markup=True,
        )

        if self._config is None:
            yield Static("[#f38ba8]No configuration loaded[/]", markup=True)
            return

        cfg = self._config

        # General
        yield Collapsible(
            Static(
                _render_section(
                    {
                        "Offline": cfg.offline,
                        "Debug": cfg.debug,
                    }
                ),
                markup=True,
            ),
            title="General",
        )

        # AWS
        yield Collapsible(
            Static(
                _render_section(
                    {
                        "S3 Bucket": cfg.aws.s3_bucket,
                        "Region": cfg.aws.region,
                        "Profile": _aws_profile_display(cfg.aws.profile),
                        "Repos Table": cfg.aws.dynamodb_repos_table,
                        "Archives Table": cfg.aws.dynamodb_archives_table,
                    }
                ),
                markup=True,
            ),
            title="AWS",
        )

        # Borg (exclude passphrases)
        yield Collapsible(
            Static(
                _render_section(
                    {
                        "Compression": cfg.borg.compression,
                        "Storage Quota": cfg.borg.storage_quota,
                        "Free Space": cfg.borg.additional_free_space,
                        "Checkpoint": f"{cfg.borg.checkpoint_interval}s",
                        "Executable": cfg.borg.executable_path,
                        "Repo Path": str(cfg.borg.default_repo_path),
                    }
                ),
                markup=True,
            ),
            title="Borg",
        )

        # Retention
        retention = cfg.borg.retention
        yield Collapsible(
            Static(
                _render_section(
                    {
                        "Daily": str(retention.keep_daily),
                        "Weekly": str(retention.keep_weekly),
                        "Monthly": str(retention.keep_monthly),
                        "Yearly": str(retention.keep_yearly),
                    }
                ),
                markup=True,
            ),
            title="Retention",
        )

        # UI
        yield Collapsible(
            Static(
                _render_section(
                    {
                        "Theme": cfg.ui.theme,
                        "Progress": cfg.ui.show_progress,
                        "Color": cfg.ui.color_output,
                        "Table Style": cfg.ui.table_style,
                    }
                ),
                markup=True,
            ),
            title="UI",
        )
