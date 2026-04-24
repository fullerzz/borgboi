"""Dedicated repository configuration editor screen for the BorgBoi TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Rule, Static

from borgboi.core.logging import get_logger
from borgboi.core.models import RetentionPolicy
from borgboi.tui.repo_workspace import load_repo_workspace_state

logger = get_logger(__name__)

if TYPE_CHECKING:
    from borgboi.config import Config
    from borgboi.core.models import Repository
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo

    RepoRecord = BorgBoiRepo | Repository


def _render_value(value: object) -> str:
    """Render a field value as escaped markup."""
    if value is None:
        return "[#6c7086]Unknown[/]"
    return f"[#cdd6f4]{escape(str(value))}[/]"


def _render_fields(fields: list[tuple[str, object]]) -> str:
    """Format key-value pairs as multiline Rich markup."""
    return "\n".join(f"[#89b4fa]{escape(label)}:[/] {_render_value(value)}" for label, value in fields)


def effective_quota_display(
    *,
    quota_load_failed: bool,
    is_local_repo: bool,
    live_quota: str | None,
    config_default_quota: str | None,
) -> tuple[str, str]:
    """Return (quota_text, source_label) for the current repository quota state.

    Shared logic used by both the info and config screens.
    """
    if quota_load_failed and is_local_repo and live_quota is None:
        return "Unknown", "Unavailable"
    if live_quota is not None:
        return live_quota, "Repository"
    if not is_local_repo:
        return "Unknown", "Unavailable"
    if config_default_quota is not None:
        return config_default_quota, "Default"
    return "Unknown", "Unknown"


@dataclass(frozen=True, slots=True)
class RepoConfigResult:
    """Final repository config state returned to the parent screen."""

    quota: str | None
    retention_policy: RetentionPolicy | None
    quota_load_failed: bool
    quota_load_error: str | None


class RepoConfigScreen(Screen[RepoConfigResult | None]):
    """Full-screen editor for repository quota and retention settings."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    def __init__(
        self,
        repo: RepoRecord,
        orchestrator: Orchestrator,
        config: Config | None = None,
        **kwargs: str | None,
    ) -> None:
        super().__init__(**kwargs)
        self._repo = repo
        self._orchestrator = orchestrator
        self._config = config or orchestrator.config
        self._config_saving = False
        self._quota_loading = False
        self._quota_load_failed = False
        self._quota_load_error: str | None = None
        self._live_quota: str | None = None

    @override
    def compose(self) -> ComposeResult:
        """Build the repo settings editor screen."""
        yield Header()
        with Vertical(id="repo-config-screen"):
            with Horizontal(id="repo-config-header"):
                with Vertical():
                    yield Static(
                        f"[bold #cba6f7]Edit repo settings: {escape(self._repo.name)}[/]",
                        id="repo-config-title",
                        markup=True,
                    )
                    yield Static(
                        _render_fields(
                            [
                                ("Path", self._repo.path),
                                ("Host", self._repo.hostname),
                                ("Quota Editable", "Yes" if self._is_local_repo() else "No"),
                            ]
                        ),
                        id="repo-config-summary",
                        markup=True,
                    )
                with Vertical():
                    yield Static("", id="repo-config-current", markup=True)
            yield Label("", id="repo-config-status", markup=True)
            yield Rule(line_style="dashed")
            with Vertical(id="repo-config-form"):
                with Horizontal(classes="repo-config-row"):
                    yield Label("Storage quota:", id="repo-config-quota-label", classes="repo-config-label")
                    yield Input(placeholder="e.g., 200G, 1.5T", id="repo-config-quota-input")
                with Horizontal(classes="repo-config-row"):
                    yield Label("Keep daily:", id="repo-config-daily-label", classes="repo-config-label")
                    yield Input(placeholder="7", id="repo-config-daily-input")
                with Horizontal(classes="repo-config-row"):
                    yield Label("Keep weekly:", id="repo-config-weekly-label", classes="repo-config-label")
                    yield Input(placeholder="4", id="repo-config-weekly-input")
                with Horizontal(classes="repo-config-row"):
                    yield Label("Keep monthly:", id="repo-config-monthly-label", classes="repo-config-label")
                    yield Input(placeholder="6", id="repo-config-monthly-input")
                with Horizontal(classes="repo-config-row"):
                    yield Label("Keep yearly:", id="repo-config-yearly-label", classes="repo-config-label")
                    yield Input(placeholder="0", id="repo-config-yearly-input")
                with Horizontal(id="repo-config-actions"):
                    yield Button("Save", id="repo-config-save-btn", variant="primary")
                    yield Button("Cancel", id="repo-config-cancel-btn")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the form and load the live quota if applicable."""
        self._populate_form()
        self._refresh_current_summary()
        self._apply_form_state()
        self._update_status_message()
        self._focus_primary_input()
        if self._is_local_repo():
            self._load_live_quota()

    def action_back(self) -> None:
        """Dismiss the screen without applying changes."""
        if self._config_saving:
            return
        _ = self.dismiss(None)

    def action_save(self) -> None:
        """Validate the form and save the repository config."""
        if self._config_saving:
            return

        quota_input = self.query_one("#repo-config-quota-input", Input)
        daily_input = self.query_one("#repo-config-daily-input", Input)
        weekly_input = self.query_one("#repo-config-weekly-input", Input)
        monthly_input = self.query_one("#repo-config-monthly-input", Input)
        yearly_input = self.query_one("#repo-config-yearly-input", Input)

        quota_value = quota_input.value.strip()
        try:
            daily = int(daily_input.value.strip() or "0")
            weekly = int(weekly_input.value.strip() or "0")
            monthly = int(monthly_input.value.strip() or "0")
            yearly = int(yearly_input.value.strip() or "0")
        except ValueError:
            self.notify("Retention values must be integers", severity="warning")
            return

        if daily <= 0 and weekly <= 0 and monthly <= 0 and yearly <= 0:
            self.notify("At least one retention period must be greater than 0", severity="warning")
            return

        if quota_value and not self._is_local_repo():
            self.notify("Storage quota can only be updated for local repositories", severity="warning")
            return

        requested_quota = self._get_requested_quota(quota_value)
        requested_retention = RetentionPolicy(
            keep_daily=daily,
            keep_weekly=weekly,
            keep_monthly=monthly,
            keep_yearly=yearly,
        )
        retention_policy, clear_retention_policy = self._get_requested_retention_policy(requested_retention)

        self._config_saving = True
        self._apply_form_state()
        self._update_status_message()
        self._update_repo_config(
            storage_quota=requested_quota,
            retention_policy=retention_policy,
            clear_retention_policy=clear_retention_policy,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle save and cancel button clicks."""
        if event.button.id == "repo-config-save-btn":
            self.action_save()
        elif event.button.id == "repo-config-cancel-btn":
            self.action_back()

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Control footer action visibility while a save is in progress."""
        if action == "save":
            return not self._config_saving
        return True

    def _is_local_repo(self) -> bool:
        """Return True when the repository is browsable on this machine."""
        return load_repo_workspace_state(self._repo).can_browse

    def _can_edit_quota(self) -> bool:
        """Return True when the quota field can be edited safely."""
        return self._is_local_repo() and not self._quota_loading and not self._quota_load_failed

    def _get_requested_quota(self, quota_value: str) -> str | None:
        """Return the quota update request, or None when quota is unchanged."""
        if not self._can_edit_quota():
            return None
        current_quota = self._live_quota or ""
        if quota_value == current_quota:
            return None
        return quota_value

    def _populate_form(self) -> None:
        """Load current effective settings into the editable form."""
        effective_retention = self._repo.get_effective_retention(default=self._default_retention_policy())
        self.query_one("#repo-config-quota-input", Input).value = self._live_quota or ""
        self.query_one("#repo-config-daily-input", Input).value = str(effective_retention.keep_daily)
        self.query_one("#repo-config-weekly-input", Input).value = str(effective_retention.keep_weekly)
        self.query_one("#repo-config-monthly-input", Input).value = str(effective_retention.keep_monthly)
        self.query_one("#repo-config-yearly-input", Input).value = str(effective_retention.keep_yearly)

    def _focus_primary_input(self) -> None:
        """Focus the first editable input."""
        if self._can_edit_quota():
            self.query_one("#repo-config-quota-input", Input).focus()
        else:
            self.query_one("#repo-config-daily-input", Input).focus()

    def _apply_form_state(self) -> None:
        """Enable or disable form fields according to the current screen state."""
        can_edit_quota = self._can_edit_quota() and not self._config_saving
        quota_input = self.query_one("#repo-config-quota-input", Input)
        quota_input.disabled = not can_edit_quota
        self.query_one("#repo-config-daily-input", Input).disabled = self._config_saving
        self.query_one("#repo-config-weekly-input", Input).disabled = self._config_saving
        self.query_one("#repo-config-monthly-input", Input).disabled = self._config_saving
        self.query_one("#repo-config-yearly-input", Input).disabled = self._config_saving
        self.query_one("#repo-config-save-btn", Button).disabled = self._config_saving
        self.query_one("#repo-config-cancel-btn", Button).disabled = self._config_saving

    def _default_retention_policy(self) -> RetentionPolicy:
        """Return the configured default retention policy."""
        if self._config is None:
            return RetentionPolicy()
        return RetentionPolicy(
            keep_daily=self._config.borg.retention.keep_daily,
            keep_weekly=self._config.borg.retention.keep_weekly,
            keep_monthly=self._config.borg.retention.keep_monthly,
            keep_yearly=self._config.borg.retention.keep_yearly,
        )

    def _get_requested_retention_policy(
        self, requested_retention: RetentionPolicy
    ) -> tuple[RetentionPolicy | None, bool]:
        """Return the semantic retention update requested by the form."""
        current_override = self._repo.retention_policy
        default_retention = self._default_retention_policy()

        if current_override is None:
            if requested_retention == default_retention:
                return None, False
            return requested_retention, False

        if requested_retention == current_override:
            return None, False
        if requested_retention == default_retention:
            return None, True
        return requested_retention, False

    def _effective_quota_display(self) -> tuple[str, str]:
        """Return the quota text and source label for the current repository state."""
        return effective_quota_display(
            quota_load_failed=self._quota_load_failed,
            is_local_repo=self._is_local_repo(),
            live_quota=self._live_quota,
            config_default_quota=self._config.borg.storage_quota if self._config is not None else None,
        )

    def _refresh_current_summary(self) -> None:
        """Refresh the current effective settings summary."""
        default_policy = self._default_retention_policy()
        repo_retention = self._repo.retention_policy
        active_policy = repo_retention or default_policy

        quota_display, quota_source = self._effective_quota_display()

        self.query_one("#repo-config-current", Static).update(
            _render_fields(
                [
                    ("Current Quota", quota_display),
                    ("Quota Source", quota_source),
                    ("Retention Source", "Repo-specific" if repo_retention is not None else "Default"),
                    ("Keep Daily", active_policy.keep_daily),
                    ("Keep Weekly", active_policy.keep_weekly),
                    ("Keep Monthly", active_policy.keep_monthly),
                    ("Keep Yearly", active_policy.keep_yearly),
                ]
            )
        )

    def _update_status_message(self) -> None:
        """Refresh the explanatory status text under the form summary."""
        status = self.query_one("#repo-config-status", Label)
        if self._config_saving:
            status.update("[dim]Saving configuration...[/]")
        elif not self._is_local_repo():
            status.update(
                "[dim]Retention can be edited here. Storage quota is only editable for local repositories.[/]"
            )
        elif self._quota_loading:
            status.update("[dim]Loading current repository quota. Retention settings are already editable.[/]")
        elif self._quota_load_failed and self._quota_load_error is not None:
            status.update(
                f"[#f38ba8]Unable to load live quota:[/] {escape(self._quota_load_error)} [dim]Retention can still be updated, but quota editing stays disabled until quota reload succeeds.[/]"
            )
        elif self._live_quota is not None:
            status.update("[dim]Editing repository-specific settings. Press Ctrl+S or use Save when ready.[/]")
        else:
            status.update(
                "[dim]No repository-specific quota is configured. Leave the quota field blank to keep using the default.[/]"
            )

    @work(thread=True)
    def _load_live_quota(self) -> None:
        """Load the current live storage quota for the repository."""
        logger.debug("Loading live storage quota for repo config screen", repo_name=self._repo.name)
        self._quota_loading = True
        self.app.call_from_thread(self._update_status_message)
        self.app.call_from_thread(self._apply_form_state)
        try:
            quota = self._orchestrator.get_repo_storage_quota(self._repo.name)
        except Exception as exc:
            logger.warning("Failed to load live storage quota", repo_name=self._repo.name, error=str(exc))
            self.app.call_from_thread(self._on_quota_load_error, exc)
            return
        finally:
            self._quota_loading = False

        self.app.call_from_thread(self._on_quota_load_success, quota)

    def _on_quota_load_success(self, quota: str | None) -> None:
        """Apply a successful quota load to the editor state."""
        self._live_quota = quota
        self._quota_load_failed = False
        self._quota_load_error = None
        self.query_one("#repo-config-quota-input", Input).value = quota or ""
        self._refresh_current_summary()
        self._apply_form_state()
        self._update_status_message()
        self._focus_primary_input()

    def _on_quota_load_error(self, error: Exception) -> None:
        """Apply a quota load failure to the editor state."""
        self._live_quota = None
        self._quota_load_failed = True
        self._quota_load_error = str(error)
        self.query_one("#repo-config-quota-input", Input).value = ""
        self._refresh_current_summary()
        self._apply_form_state()
        self._update_status_message()
        self._focus_primary_input()

    @work(thread=True, exclusive=True)
    def _update_repo_config(
        self,
        *,
        storage_quota: str | None,
        retention_policy: RetentionPolicy | None,
        clear_retention_policy: bool,
    ) -> None:
        """Persist the updated repository settings in a worker thread."""
        logger.info(
            "Updating repository configuration from config screen",
            repo_name=self._repo.name,
            storage_quota=storage_quota,
            retention=(
                None
                if retention_policy is None
                else (
                    f"D{retention_policy.keep_daily}/W{retention_policy.keep_weekly}/"
                    f"M{retention_policy.keep_monthly}/Y{retention_policy.keep_yearly}"
                )
            ),
            clear_retention_policy=clear_retention_policy,
        )
        try:
            updated_quota, updated_retention = self._orchestrator.update_repo_config(
                name=self._repo.name,
                storage_quota=storage_quota,
                retention_policy=retention_policy,
                clear_retention_policy=clear_retention_policy,
            )
        except Exception as exc:
            logger.exception("Failed to update repository configuration", repo_name=self._repo.name, error=str(exc))
            self.app.call_from_thread(self._on_config_update_error, exc)
            return

        self.app.call_from_thread(self._on_config_update_success, storage_quota, updated_quota, updated_retention)

    def _on_config_update_success(
        self,
        requested_quota: str | None,
        updated_quota: str | None,
        updated_retention: RetentionPolicy | None,
    ) -> None:
        """Dismiss the screen with the final updated state."""
        self._config_saving = False
        if requested_quota is not None:
            final_quota = updated_quota
            quota_load_failed = False
            quota_load_error = None
        else:
            final_quota = self._live_quota
            quota_load_failed = self._quota_load_failed
            quota_load_error = self._quota_load_error

        _ = self.dismiss(
            RepoConfigResult(
                quota=final_quota,
                retention_policy=updated_retention,
                quota_load_failed=quota_load_failed,
                quota_load_error=quota_load_error,
            )
        )

    def _on_config_update_error(self, error: Exception) -> None:
        """Restore the form after a failed save attempt."""
        self._config_saving = False
        self._apply_form_state()
        self.query_one("#repo-config-status", Label).update(
            f"[#f38ba8]Failed to save configuration:[/] {escape(str(error))}"
        )
        self.notify(str(error), severity="error", title="Config Update Failed")
