"""Configuration viewer screen for the BorgBoi TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from borgboi.core.logging import get_logger
from borgboi.tui.config_panel import ConfigPanel

logger = get_logger(__name__)

if TYPE_CHECKING:
    from borgboi.config import Config


class ConfigScreen(Screen[None]):
    """Full-screen view of the borgboi configuration."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, config: Config | None = None, **kwargs: str | None) -> None:
        super().__init__(**kwargs)
        self._config = config
        logger.debug("ConfigScreen initialized", has_config=config is not None)

    @override
    def compose(self) -> ComposeResult:
        """Build the config screen layout."""
        yield Header()
        with Vertical(id="config-screen"):
            yield ConfigPanel(config=self._config)
        yield Footer()

    def action_back(self) -> None:
        """Return to the main screen."""
        logger.debug("Closing config screen")
        _ = self.app.pop_screen()
