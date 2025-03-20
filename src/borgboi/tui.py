import json
from typing import Any

from rich.columns import Columns
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Grid, ScrollableContainer, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Header, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from borgboi import orchestrator

COMMAND_OPTIONS = [
    {"name": "list-repos", "description": "List all BorgBoi repositories"},
    {"name": "repo-info", "description": "Get info about a specific repository"},
    {"name": "create-repo", "description": "Create a new Borg repository"},
    {"name": "create-exclusions", "description": "Create a new exclusions list for a Borg repository"},
    {"name": "list-archives", "description": "List the archives in a Borg repository"},
    {"name": "get-repo", "description": "Get a Borg repository by name or path"},
    {"name": "daily-backup", "description": "Perform a daily backup"},
    {"name": "restore", "description": "Restore a Borg repository"},
    {"name": "delete-repo", "description": "Delete a Borg repository"},
    {"name": "delete-archive", "description": "Delete an archive from a Borg repository"},
]


class CommandInputScreen(ModalScreen[dict[str, str]]):
    """Screen with a dialog to quit."""

    CSS_PATH = "tcss/modal.tcss"

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Enter the name of the repo:", id="repo-name-label"),
            Input(placeholder="repo name", id="repo-name-input"),
            Button("Confirm", variant="primary", id="confirm"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss({"repo_name": self.query_one("#repo-name-input", Input).value})
        else:
            self.dismiss(None)


class CommandPicker(Widget):
    class Output(Message):
        """Command output message."""

        def __init__(self, output: str | Table | Columns) -> None:
            self.output = output
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("⚡️ [bold]Command Picker[/]", id="command-picker-label")
        yield OptionList()  # TODO: Update selected option highlight color

    def on_mount(self) -> None:
        """
        Populate the option list with command options.
        """
        options_list = self.query_one(OptionList)
        for option in COMMAND_OPTIONS:
            prompt = f"[bold #a6e3a1] {option['name']}[/] - [#74c7ec]{option['description']}[/]"
            options_list.add_option(Option(prompt=prompt, id=option["name"]))
        options_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """
        Handle option selection from the OptionList and call the appropriate BorgBoi function.
        """

        def handle_command_input(inputs: dict[str, str] | None) -> None:
            if inputs is None:
                self.app.notify("CommandInputScreen cancelled")
                return
            else:
                self.app.notify(json.dumps(inputs))
                repo_info_panels = orchestrator.get_repo_info_tui(None, inputs["repo_name"])
                self.post_message(
                    self.Output(repo_info_panels),  # pyright: ignore
                )

        match event.option.id:
            case "list-repos":
                self.app.notify("list-repos selected")
                repos_table = orchestrator.get_repos_table()
                self.post_message(
                    self.Output(repos_table),  # pyright: ignore
                )
            case "repo-info":
                self.app.notify("repo-info selected")
                self.app.push_screen(CommandInputScreen(), handle_command_input)
            case _:
                self.app.notify("Unknown option selected", severity="error")


class BorgBoiTui(App[Any]):
    CSS_PATH = "tcss/app.tcss"

    def on_mount(self) -> None:
        self.theme = "catppuccin-mocha"

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            yield Header(True, name="BorgBoi", icon="👦🏼")
            with Vertical(classes="row topPanel"):
                yield CommandPicker(classes="column")
            yield Static("Output placeholder", id="output", classes="row bottomPanel")

    def on_command_picker_output(self, event: CommandPicker.Output) -> None:
        self.query_one("#output", Static).update(event.output)


if __name__ == "__main__":
    app = BorgBoiTui()
    app.run()
