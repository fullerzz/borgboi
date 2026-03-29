"""Configuration viewer screen for the BorgBoi TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from borgboi.tui.config_panel import ConfigPanel

if TYPE_CHECKING:
    from borgboi.config import Config


class ConfigScreen(Screen[None]):
    """Full-screen view of the borgboi configuration."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, config: Config | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = config

    @override
    def compose(self) -> ComposeResult:
        """Build the config screen layout."""
        yield Header()
        with Vertical(id="config-screen"):
            yield ConfigPanel(config=self._config)
        yield Footer()

    def action_back(self) -> None:
        """Return to the main screen."""
        _ = self.app.pop_screen()
