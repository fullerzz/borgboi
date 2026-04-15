"""Repository detail screen for the BorgBoi TUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, override

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Label,
    Rule,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from borgboi.clients.borg import RepoArchive, RepoInfo
from borgboi.core.logging import get_logger
from borgboi.core.models import RetentionPolicy
from borgboi.lib.utils import calculate_archive_age, format_iso_timestamp, format_last_backup, format_repo_size
from borgboi.tui.repo_config_screen import RepoConfigResult, RepoConfigScreen, effective_quota_display
from borgboi.tui.repo_workspace import load_repo_workspace_state

logger = get_logger(__name__)

if TYPE_CHECKING:
    from borgboi.config import Config
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.models import BorgBoiRepo


@dataclass(frozen=True, slots=True)
class RepoExcludesState:
    """The effective excludes document for a repository."""

    source_label: str
    status: str
    path: Path | None
    body: str


def _render_value(value: object) -> str:
    """Render a field value as escaped markup."""
    if value is None:
        return "[#6c7086]Unknown[/]"
    if isinstance(value, bool):
        return f"[#cdd6f4]{'Yes' if value else 'No'}[/]"
    return f"[#cdd6f4]{escape(str(value))}[/]"


def _render_fields(fields: list[tuple[str, object]]) -> str:
    """Format key-value pairs as multiline Rich markup."""
    return "\n".join(f"[#89b4fa]{escape(label)}:[/] {_render_value(value)}" for label, value in fields)


def _format_datetime(value: datetime | None) -> str:
    """Format datetimes for the TUI detail view."""
    if value is None:
        return "Unknown"
    return value.astimezone(UTC).strftime("%a, %Y-%m-%d %H:%M:%S UTC")


def _format_archive_age(archive_name: str) -> str:
    """Format the age of an archive, tolerating non-standard names."""
    try:
        return calculate_archive_age(archive_name)
    except ValueError:
        return "Unknown"


def _escape_text(value: object) -> str:
    """Escape a value for Rich markup output."""
    return escape(str(value))


def _read_document(path: Path) -> str:
    """Read a text document for display."""
    return path.read_text(encoding="utf-8")


def _load_excludes_document(path: Path, source_label: str, active_status: str, empty_status: str) -> RepoExcludesState:
    """Load an excludes document without letting read failures break the screen."""
    try:
        body = _read_document(path)
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning(
            "Failed to read excludes document",
            path=path.as_posix(),
            source=source_label,
            error=str(exc),
        )
        return RepoExcludesState(
            source_label=source_label,
            status=f"{source_label} excludes file could not be read: {exc}",
            path=path,
            body="",
        )

    return RepoExcludesState(
        source_label=source_label,
        status=active_status if body else empty_status,
        path=path,
        body=body,
    )


def load_repo_excludes_state(config: Config | None, repo_name: str) -> RepoExcludesState:
    """Resolve the excludes file currently in effect for a repository."""
    if config is None:
        return RepoExcludesState(
            source_label="Unavailable",
            status="No configuration loaded, so BorgBoi could not resolve excludes for this repository.",
            path=None,
            body="",
        )

    repo_specific_path = config.borgboi_dir / f"{repo_name}_{config.excludes_filename}"
    default_path = config.borgboi_dir / config.excludes_filename

    if repo_specific_path.exists():
        return _load_excludes_document(
            repo_specific_path,
            "Repo-specific",
            "Repo-specific excludes override the shared default for this repository.",
            "Repo-specific excludes file is empty and overrides the shared default for this repository.",
        )

    if default_path.exists():
        return _load_excludes_document(
            default_path,
            "Shared default",
            "Shared default excludes are currently in use for this repository.",
            "Shared default excludes file is empty and currently in use for this repository.",
        )

    return RepoExcludesState(
        source_label="Missing",
        status="No repo-specific excludes file found, and no shared default excludes file is available.",
        path=None,
        body="",
    )


class RepoInfoScreen(Screen[None]):
    """Screen for viewing repository-specific details."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Back"),
        Binding("a", "show_archives", "Archives"),
        Binding("b", "daily_backup", "Backup"),
        Binding("d", "compare_archives", "Compare"),
        Binding("e", "edit_config", "Edit Config"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(
        self,
        repo: BorgBoiRepo,
        orchestrator: Orchestrator,
        config: Config | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._repo = repo
        self._orchestrator = orchestrator
        self._config = config or orchestrator.config
        self._workspace_state = load_repo_workspace_state(repo)
        self._live_quota: str | None = None
        self._quota_load_failed = False
        self._quota_loading = False
        self._quota_load_error: str | None = None

    @override
    def compose(self) -> ComposeResult:
        """Build the repository detail layout."""
        excludes_viewer = TextArea("", id="repo-info-excludes-viewer")
        excludes_viewer.read_only = True

        yield Header()
        with VerticalScroll(id="repo-info-screen"):
            yield Label(
                f"[bold #cba6f7]Repository info: {escape(self._repo.name)}[/]",
                id="repo-info-title",
                markup=True,
            )
            yield Label("Loading live repository data...", id="repo-info-loading")
            yield Label("", id="repo-info-hero", markup=True)
            yield Rule(id="repo-info-divider")

            with TabbedContent(initial="repo-info-overview-tab", id="repo-info-tabs"):
                with (
                    TabPane("Overview", id="repo-info-overview-tab"),
                    VerticalScroll(id="repo-info-overview-body", classes="repo-info-tab-body"),
                ):
                    with Horizontal(classes="repo-info-card-row"):
                        yield Static("", id="repo-info-last-backup-card", classes="repo-info-card", markup=True)
                        yield Static("", id="repo-info-storage-card", classes="repo-info-card", markup=True)
                    with Horizontal(classes="repo-info-card-row"):
                        yield Static("", id="repo-info-retention-card", classes="repo-info-card", markup=True)
                        yield Static("", id="repo-info-sync-card", classes="repo-info-card", markup=True)

                    with Collapsible(title="Repository profile", classes="repo-info-collapsible"):
                        yield Label("", id="repo-info-summary", markup=True)

                with (
                    TabPane("Repo Settings", id="repo-info-settings-tab"),
                    VerticalScroll(id="repo-info-settings-body", classes="repo-info-tab-body"),
                ):
                    yield Label("", id="repo-info-config", markup=True)
                    with Horizontal(id="repo-info-config-actions", classes="repo-info-config-actions"):
                        yield Button("Edit settings", id="repo-info-edit-config-btn", variant="primary")
                    yield Label("", id="repo-info-config-status", markup=True)

                with TabPane("Live Borg", id="repo-info-live-tab"), Vertical(classes="repo-info-tab-body"):
                    yield Label("Loading live Borg metadata...", id="repo-info-live-summary", markup=True)
                    with Horizontal(classes="repo-info-card-row"):
                        yield Static("", id="repo-info-live-size-card", classes="repo-info-card", markup=True)
                        yield Static("", id="repo-info-live-security-card", classes="repo-info-card", markup=True)
                    yield Rule(classes="repo-info-pane-divider")
                    yield Label("Loading live Borg metadata...", id="repo-info-command-output", markup=True)

                with TabPane("Archives", id="repo-info-archives-tab"), Vertical(classes="repo-info-tab-body"):
                    yield Label("", id="repo-info-archives-status")
                    with Horizontal(id="repo-info-archives-actions"):
                        yield Button(
                            "Compare archives",
                            id="repo-info-compare-archives-btn",
                            variant="primary",
                            disabled=not self._is_local_repo(),
                        )
                    yield DataTable(id="repo-info-archives-table")

                with (
                    TabPane("Protection", id="repo-info-protection-tab"),
                    Vertical(classes="repo-info-tab-body"),
                    Collapsible(title="Excludes in use", classes="repo-info-collapsible"),
                    Vertical(classes="repo-info-protection-block"),
                ):
                    yield Label("", id="repo-info-excludes-status", markup=True)
                    yield Label("", id="repo-info-excludes-path", markup=True)
                    yield excludes_viewer

                with TabPane("Workspace", id="repo-info-workspace-tab"), Vertical(classes="repo-info-tab-body"):
                    yield Label("", id="repo-info-workspace-status", markup=True)
                    yield Label("", id="repo-info-workspace-path", markup=True)
                    if self._workspace_state.can_browse:
                        yield DirectoryTree(self._workspace_state.path, id="repo-info-workspace-tree")
                    else:
                        yield Static("", id="repo-info-workspace-unavailable", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        """Configure the screen widgets and start loading live data."""
        table = self.query_one("#repo-info-archives-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Name", "Created", "Age", "ID")
        self._render_static_sections()
        self._load_repo_details()
        if self._is_local_repo():
            self.query_one("#repo-info-config-status", Label).update("[dim]Loading current repository quota...[/]")
            self._load_live_quota()
        else:
            self._apply_remote_quota_state()

    def action_back(self) -> None:
        """Return to the previous screen."""
        _ = self.app.pop_screen()

    def action_daily_backup(self) -> None:
        """Open the daily backup screen with the current repo pre-selected."""
        from borgboi.tui.daily_backup_screen import DailyBackupScreen

        _ = self.app.push_screen(
            DailyBackupScreen(
                orchestrator=self._orchestrator,
                selected_repo_name=self._repo.name,
            )
        )

    def action_refresh(self) -> None:
        """Reload the live repository details."""
        logger.debug("Refreshing repo info screen", repo_name=self._repo.name)
        self.query_one("#repo-info-loading", Static).update("Refreshing live repository data...")
        self.query_one("#repo-info-command-output", Static).update("Refreshing live Borg metadata...")
        if self._is_local_repo():
            self._live_quota = None
            self._quota_load_failed = False
            self._quota_load_error = None
            self._refresh_quota_display()
            self.query_one("#repo-info-config-status", Label).update("[dim]Reloading config...[/]")
        else:
            self._apply_remote_quota_state()

        self._load_repo_details()
        if self._is_local_repo():
            self._load_live_quota()

    def action_compare_archives(self) -> None:
        """Open the archive compare screen for the current repository."""
        if not self._is_local_repo():
            self.notify("Archive comparison is only available for repositories on this machine.", severity="warning")
            return

        table = self.query_one("#repo-info-archives-table", DataTable)
        if table.row_count < 2:
            self.notify("This repository needs at least two archives to compare.", severity="warning")
            return

        from borgboi.tui.archive_compare_screen import ArchiveCompareScreen

        older_archive, newer_archive = self._default_compare_archives()
        _ = self.app.push_screen(
            ArchiveCompareScreen(
                repo=self._repo,
                orchestrator=self._orchestrator,
                initial_older_archive=older_archive,
                initial_newer_archive=newer_archive,
            )
        )

    def action_show_archives(self) -> None:
        """Open the Archives tab and focus the archive table."""
        self.query_one("#repo-info-tabs", TabbedContent).active = "repo-info-archives-tab"
        self.query_one("#repo-info-archives-table", DataTable).focus()

    def action_edit_config(self) -> None:
        """Open the dedicated repo settings editor screen."""
        self._wait_for_config_result()

    @work(exclusive=True)
    async def _wait_for_config_result(self) -> None:
        """Wait for the config editor to dismiss and apply any result."""
        result = await self.app.push_screen_wait(
            RepoConfigScreen(repo=self._repo, orchestrator=self._orchestrator, config=self._config)
        )
        if result is not None:
            self._apply_config_result(result)

    def _render_static_sections(self) -> None:
        """Render the repository sections that come from local BorgBoi state."""
        self.query_one("#repo-info-hero", Static).update(self._render_repo_hero())
        self._render_overview_cards()
        self.query_one("#repo-info-summary", Static).update(self._render_repo_summary())
        self.query_one("#repo-info-config", Static).update(self._render_quota_and_retention())
        self.query_one("#repo-info-workspace-status", Static).update(
            _render_fields([("Status", self._workspace_state.status)])
        )
        self.query_one("#repo-info-workspace-path", Static).update(
            _render_fields([("Path", self._workspace_state.path.as_posix())])
        )
        if not self._workspace_state.can_browse:
            self.query_one("#repo-info-workspace-unavailable", Static).update(
                f"[#f9e2af]{escape(self._workspace_state.detail)}[/]"
            )

        excludes = load_repo_excludes_state(self._config, self._repo.name)
        self.query_one("#repo-info-excludes-status", Static).update(
            _render_fields(
                [
                    ("Source", excludes.source_label),
                    ("Status", excludes.status),
                ]
            )
        )
        self.query_one("#repo-info-excludes-path", Static).update(
            _render_fields([("Path", excludes.path.as_posix() if excludes.path else "None")])
        )
        self.query_one("#repo-info-excludes-viewer", TextArea).load_text(excludes.body)

    def _is_local_repo(self) -> bool:
        """Check if the repository is local to this machine."""
        return self._workspace_state.can_browse

    def _refresh_quota_display(self) -> None:
        """Refresh both quota displays to reflect the current state."""
        self._render_overview_cards()
        self.query_one("#repo-info-config", Static).update(self._render_quota_and_retention())

    def _effective_quota_display(self) -> tuple[str, str]:
        """Return the quota text and source label for the current repository state."""
        return effective_quota_display(
            quota_load_failed=self._quota_load_failed,
            is_local_repo=self._is_local_repo(),
            live_quota=self._live_quota,
            config_default_quota=self._config.borg.storage_quota if self._config is not None else None,
        )

    def _apply_remote_quota_state(self) -> None:
        """Show the read-only quota state for repositories on another machine."""
        self.query_one("#repo-info-config-status", Label).update(
            "[dim]Press e or use Edit settings to update retention. Storage quota is only editable for local repositories.[/]"
        )

    @work(thread=True)
    def _load_live_quota(self) -> None:
        """Load the live storage quota for the repository in a worker thread."""
        logger.debug("Loading live storage quota", repo_name=self._repo.name)
        self._quota_loading = True
        try:
            quota = self._orchestrator.get_repo_storage_quota(self._repo)
        except Exception as exc:
            logger.warning("Failed to load live storage quota", repo_name=self._repo.name, error=str(exc))
            self.app.call_from_thread(self._on_quota_load_error, exc)
            return
        finally:
            self._quota_loading = False

        self.app.call_from_thread(self._on_quota_load_success, quota)

    def _on_quota_load_success(self, quota: str | None) -> None:
        """Handle successful live quota load."""
        self._live_quota = quota
        self._quota_load_failed = False
        self._quota_load_error = None
        self._refresh_quota_display()
        status_widget = self.query_one("#repo-info-config-status", Label)
        if quota:
            status_widget.update("[dim]Press e or use Edit settings to update quota and retention.[/]")
        else:
            status_widget.update(
                "[dim]No repository-specific quota configured. Press e or use Edit settings to update quota and retention.[/]"
            )

    def _on_quota_load_error(self, error: Exception) -> None:
        """Handle live quota load failure."""
        self._live_quota = None
        self._quota_load_failed = True
        self._quota_load_error = str(error)
        self._refresh_quota_display()
        self.query_one("#repo-info-config-status", Label).update(
            f"[#f38ba8]Unable to load live quota:[/] {escape(str(error))} [dim]Press e or use Edit settings to update retention. Quota editing stays disabled until quota reload succeeds.[/]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the repo info screen."""
        if event.button.id == "repo-info-edit-config-btn":
            self.action_edit_config()
            return
        if event.button.id == "repo-info-compare-archives-btn":
            self.action_compare_archives()

    def _apply_config_result(self, result: RepoConfigResult) -> None:
        """Apply the config editor result to the parent summary state."""
        self._live_quota = result.quota
        self._quota_load_failed = result.quota_load_failed
        self._quota_load_error = result.quota_load_error
        self._repo.retention_policy = result.retention_policy
        self._refresh_quota_display()

        if result.quota_load_failed and result.quota_load_error is not None:
            self.query_one("#repo-info-config-status", Label).update(
                f"[#f38ba8]Live quota still unavailable:[/] {escape(result.quota_load_error)} [dim]Press e or use Edit settings to retry later.[/]"
            )
        else:
            self.query_one("#repo-info-config-status", Label).update(
                "[dim]Repository settings updated. Press e or use Edit settings to make more changes.[/]"
            )

        self.notify("Configuration saved", severity="information", title="Config Updated")

    def _render_info_card(self, title: str, value: str, detail: str, *, accent: str = "#89b4fa") -> str:
        """Render a compact card-like summary block."""
        return "\n".join(
            [
                f"[{accent}]{escape(title)}[/]",
                f"[bold #f5e0dc]{escape(value)}[/]",
                f"[#a6adc8]{escape(detail)}[/]",
            ]
        )

    def _render_repo_hero(self) -> str:
        """Render the hero summary shown above the tabbed content."""
        return "\n".join(
            [
                f"[bold #f5e0dc]{escape(self._repo.name)}[/] [#a6e3a1]on {escape(self._repo.hostname)}[/]",
                f"[#89b4fa]{escape(self._repo.path)}[/]",
                (f"[#bac2de]Backing up {escape(self._repo.backup_target)} from {escape(self._repo.os_platform)}[/]"),
            ]
        )

    def _render_overview_cards(self) -> None:
        """Populate the overview cards with stored repository state."""
        if self._config is not None:
            default_policy = RetentionPolicy(
                keep_daily=self._config.borg.retention.keep_daily,
                keep_weekly=self._config.borg.retention.keep_weekly,
                keep_monthly=self._config.borg.retention.keep_monthly,
                keep_yearly=self._config.borg.retention.keep_yearly,
            )
        else:
            default_policy = RetentionPolicy()

        quota, _quota_source = self._effective_quota_display()

        repo_retention = self._repo.retention_policy
        active_policy = repo_retention or default_policy
        sync_display = _format_datetime(self._repo.last_s3_sync)

        self.query_one("#repo-info-last-backup-card", Static).update(
            self._render_info_card(
                "Last backup",
                format_last_backup(self._repo.last_backup),
                f"Target {self._repo.backup_target}",
                accent="#89dceb",
            )
        )
        self.query_one("#repo-info-storage-card", Static).update(
            self._render_info_card(
                "Stored size",
                format_repo_size(self._repo.metadata),
                f"Quota {quota}",
                accent="#f9e2af",
            )
        )
        self.query_one("#repo-info-retention-card", Static).update(
            self._render_info_card(
                "Retention",
                "Repo-specific" if repo_retention is not None else "Default",
                (
                    "D/W/M/Y "
                    f"{active_policy.keep_daily}/{active_policy.keep_weekly}/"
                    f"{active_policy.keep_monthly}/{active_policy.keep_yearly}"
                ),
                accent="#cba6f7",
            )
        )
        self.query_one("#repo-info-sync-card", Static).update(
            self._render_info_card(
                "Last S3 sync",
                sync_display,
                f"Created {_format_datetime(self._repo.created_at)}",
                accent="#a6e3a1",
            )
        )

    def _render_repo_summary(self) -> str:
        """Render stored BorgBoi repository metadata."""
        metadata = self._repo.metadata
        fields: list[tuple[str, object]] = [
            ("Name", self._repo.name),
            ("Path", self._repo.path),
            ("Backup Target", self._repo.backup_target),
            ("Hostname", self._repo.hostname),
            ("Platform", self._repo.os_platform),
            ("Last Backup", format_last_backup(self._repo.last_backup)),
            ("Last S3 Sync", _format_datetime(self._repo.last_s3_sync)),
            ("Created", _format_datetime(self._repo.created_at)),
            ("Stored Size", format_repo_size(metadata)),
            ("Passphrase File", self._repo.passphrase_file_path),
        ]

        if metadata is not None:
            fields.extend(
                [
                    ("Stored Repo Location", metadata.repository.location),
                    ("Stored Encryption", metadata.encryption.mode),
                    ("Stored Security Dir", metadata.security_dir),
                ]
            )

        return _render_fields(fields)

    def _render_quota_and_retention(self) -> str:
        """Render storage quota and effective prune retention settings."""
        default_policy = RetentionPolicy()
        if self._config is not None:
            default_policy = RetentionPolicy(
                keep_daily=self._config.borg.retention.keep_daily,
                keep_weekly=self._config.borg.retention.keep_weekly,
                keep_monthly=self._config.borg.retention.keep_monthly,
                keep_yearly=self._config.borg.retention.keep_yearly,
            )

        repo_retention = self._repo.retention_policy
        active_policy = repo_retention or default_policy
        retention_source = "Repo-specific" if repo_retention is not None else "Default"

        quota_display, quota_source = self._effective_quota_display()

        return _render_fields(
            [
                ("Max Storage Quota", quota_display),
                ("Quota Source", quota_source),
                ("Retention Source", retention_source),
                ("Keep Daily", active_policy.keep_daily),
                ("Keep Weekly", active_policy.keep_weekly),
                ("Keep Monthly", active_policy.keep_monthly),
                ("Keep Yearly", active_policy.keep_yearly),
            ]
        )

    @work(thread=True, exclusive=True)
    def _load_repo_details(self) -> None:
        """Load live Borg metadata and archive listings in a worker thread."""
        logger.debug("Loading live repo info", repo_name=self._repo.name, repo_path=self._repo.path)
        try:
            repo_info = self._orchestrator.get_repo_info(self._repo)
            archives = sorted(
                self._orchestrator.list_archives(self._repo),
                key=lambda archive: archive.name,
                reverse=True,
            )
        except Exception as exc:
            logger.exception("Failed to load repo info screen data", repo_name=self._repo.name, error=str(exc))
            self.app.call_from_thread(self._on_load_error, exc)
            return

        self.app.call_from_thread(self._apply_live_state, repo_info, archives)

    def _apply_live_state(self, repo_info: RepoInfo, archives: list[RepoArchive]) -> None:
        """Render the live Borg information after it has loaded."""
        self.query_one("#repo-info-loading", Static).update("Live repository data loaded.")
        self.query_one("#repo-info-live-summary", Static).update(self._render_live_summary(repo_info, archives))
        self._render_live_cards(repo_info, archives)
        self.query_one("#repo-info-command-output", Static).update(self._render_command_output(repo_info))
        self._update_archives_table(archives)

    def _render_command_output(self, repo_info: RepoInfo) -> str:
        """Render the same information surfaced by `borgboi repo info`."""
        return _render_fields(
            [
                ("Total Size", f"{repo_info.cache.total_size_gb} GB"),
                ("Compressed Size", f"{repo_info.cache.total_csize_gb} GB"),
                ("Deduplicated Size", f"{repo_info.cache.unique_csize_gb} GB"),
                ("Encryption", repo_info.encryption.mode),
                ("Location", repo_info.repository.location),
                ("Last Modified", format_iso_timestamp(repo_info.repository.last_modified)),
                ("Security Dir", repo_info.security_dir),
                ("Repo ID", repo_info.repository.id),
                ("Archive Count", len(repo_info.archives)),
                ("Cache Path", repo_info.cache.path),
            ]
        )

    def _render_live_summary(self, repo_info: RepoInfo, archives: list[RepoArchive]) -> str:
        """Render a compact summary of the live Borg metadata."""
        return "\n".join(
            [
                (
                    f"[bold #f5e0dc]{escape(repo_info.repository.location)}[/] "
                    f"[#a6e3a1]{escape(repo_info.encryption.mode)}[/]"
                ),
                (
                    f"[#89b4fa]{len(archives)} live archives[/] "
                    f"[#a6adc8]Last modified {escape(format_iso_timestamp(repo_info.repository.last_modified))}[/]"
                ),
            ]
        )

    def _render_live_cards(self, repo_info: RepoInfo, archives: list[RepoArchive]) -> None:
        """Populate the live Borg metric cards."""
        self.query_one("#repo-info-live-size-card", Static).update(
            self._render_info_card(
                "Capacity",
                f"{repo_info.cache.total_size_gb} GB total",
                f"Compressed {repo_info.cache.total_csize_gb} GB | Dedup {repo_info.cache.unique_csize_gb} GB",
                accent="#89dceb",
            )
        )
        self.query_one("#repo-info-live-security-card", Static).update(
            self._render_info_card(
                "Security",
                repo_info.encryption.mode,
                f"Repo {repo_info.repository.id[:12]} | Archives {len(archives)}",
                accent="#f38ba8",
            )
        )

    def _update_archives_table(self, archives: list[RepoArchive]) -> None:
        """Refresh the archive table with the live archive listing."""
        table = self.query_one("#repo-info-archives-table", DataTable)
        table.clear()

        if not archives:
            self.query_one("#repo-info-archives-status", Static).update("No archives found for this repository.")
            self.query_one("#repo-info-compare-archives-btn", Button).disabled = True
            return

        self.query_one("#repo-info-archives-status", Static).update(f"{len(archives)} archives found.")
        self.query_one("#repo-info-compare-archives-btn", Button).disabled = not (
            self._is_local_repo() and len(archives) >= 2
        )
        for archive in archives:
            table.add_row(
                archive.name,
                format_iso_timestamp(archive.time),
                _format_archive_age(archive.name),
                archive.id[:12],
            )

    def _default_compare_archives(self) -> tuple[str | None, str | None]:
        """Return the older/newer archive names from the current archive table selection."""
        table = self.query_one("#repo-info-archives-table", DataTable)
        rows: list[str] = []
        for row_index in range(table.row_count):
            row_key = table.get_row_at(row_index)
            rows.append(str(row_key[0]))

        if len(rows) < 2:
            return None, None

        return rows[1], rows[0]

    def _on_load_error(self, error: Exception) -> None:
        """Handle live data loading failures."""
        self.query_one("#repo-info-loading", Static).update("Failed to load live repository data.")
        self.query_one("#repo-info-live-summary", Static).update(
            f"[#f38ba8]Live Borg metadata unavailable:[/] {_escape_text(error)}"
        )
        self.query_one("#repo-info-live-size-card", Static).update(
            self._render_info_card("Capacity", "Unavailable", "Unable to query Borg right now.", accent="#f38ba8")
        )
        self.query_one("#repo-info-live-security-card", Static).update(
            self._render_info_card("Security", "Unavailable", "Archive metadata not loaded.", accent="#f38ba8")
        )
        self.query_one("#repo-info-command-output", Static).update(_render_fields([("Error", str(error))]))
        self.query_one("#repo-info-archives-status", Static).update("Archive list unavailable.")
        self.query_one("#repo-info-archives-table", DataTable).clear()
        self.query_one("#repo-info-compare-archives-btn", Button).disabled = True
        self.notify(str(error), severity="error", title="Failed to load repo info")
