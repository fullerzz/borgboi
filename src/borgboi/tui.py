from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import OptionList, Static

from borgboi import orchestrator


class CommandPicker(Widget):
    def compose(self) -> ComposeResult:
        yield OptionList(
            "list-repos",
            "repo-info",
        )
        yield Static("", id="repos-table")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.prompt == "list-repos":
            self.app.notify("list-repos selected")
            # TODO: Pass the repos table to something in the TUI that can render it
            repos_table = orchestrator.get_repos_table()
            self.query_one("#repos-table", Static).update(repos_table)
        elif event.option.prompt == "repo-info":
            self.app.notify("repo-info selected")
        else:
            self.app.notify("Unknown option selected", severity="error")


class BorgBoiTui(App[Any]):
    CSS_PATH = "tcss/app.tcss"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("BorgBoi 👦🏼", expand=True, classes="row")
            yield CommandPicker(classes="row")


if __name__ == "__main__":
    app = BorgBoiTui()
    app.run()
