# TUI

Use `bb tui` to open BorgBoi's interactive terminal dashboard.

```sh
bb tui
```

The TUI uses the same effective configuration as the CLI, so `--offline`, `--debug`, and `BORGBOI_*` overrides all apply here too.

## Home Screen

When the app starts, BorgBoi loads your managed repositories into a table with these columns:

- `Name`
- `Hostname`
- `Last Archive`
- `Size`

Below the table an **Archive Activity** sparkline shows the number of successful archive creations per day over the last 14 days.

The header subtitle indicates whether BorgBoi is running in **Online** or **Offline** mode.

### Home-Screen Keys

| Key | Action |
| --- | --- |
| `q` | Quit the app |
| `r` | Refresh the repository list and sparkline |
| `c` | Open the config viewer screen |
| `e` | Open the excludes viewer |
| `b` | Open the daily backup screen |
| `Enter` / `i` | Open the repository detail screen for the highlighted repository |

## Config Viewer

Press `c` from the home screen to open a full-screen view of the effective configuration, grouped into `General`, `AWS`, `Borg`, `Retention`, and `UI` sections.

Press `Esc` to return to the home screen.

## Repository Detail Screen

Press `Enter` or `i` from the home screen to open the repository detail screen for the highlighted repository. You can also click any row in the repository table.

The screen is organized into six tabs:

| Tab | Contents |
| --- | --- |
| **Overview** | Name, hostname, path, backup target, last archive date, and size summary |
| **Repo Settings** | Configured retention policy, storage quota, and compression settings with an inline edit action |
| **Live Borg** | On-demand `borg info` output fetched live from the repository |
| **Archives** | Scrollable list of all archives with timestamps and sizes; select an archive to view its contents |
| **Protection** | Encryption mode and key metadata |
| **Workspace** | Interactive directory tree rooted at the backup target path |

### Repository Detail Keys

| Key | Action |
| --- | --- |
| `Esc` | Return to the home screen |
| `a` | Jump to the Archives tab |
| `b` | Open the daily backup screen for this repository |
| `d` | Open the archive compare / diff view |
| `e` | Open the repo settings editor |
| `r` | Refresh the screen data |

## Archive Compare Screen

Press `d` from the repository detail screen to compare two archives from the selected repository.

BorgBoi loads the repository's archives newest-first and starts by comparing the two most recent archives. Use the **Older archive** and **Newer archive** selectors to choose a different pair, then press **Compare** or `r` to rerun the comparison.

The screen shows side-by-side directory trees for the older and newer archives. Expanding or selecting a path in one tree keeps the other tree in sync when the path exists on both sides.

### Change Indicators

- Added paths appear on the newer side.
- Removed paths appear on the older side.
- Modified paths appear on both sides.
- Parent directories with changed descendants show a dim change marker so you can follow changes through nested trees.

The center panel summarizes the comparison and shows details for the selected path, including whether the path is present in each archive and the recorded change types.

### Filters and Content Diffs

Use the numbered change-kind filters to show or hide added, removed, modified, or mode-only changes. Use the path search input to narrow the tree to matching changed paths.

Turn on **Content only** before rerunning a comparison to limit results to content changes.

Press `d` on a selected changed file to open a content diff modal. BorgBoi extracts up to 2 MiB from each archive copy and renders a unified text diff. Binary files and files above that limit are skipped instead of being rendered inline.

### Archive Compare Keys

| Key | Action |
| --- | --- |
| `Esc` | Return to the repository detail screen |
| `r` | Run the comparison for the selected archive pair |
| `n` | Jump to the next visible changed path |
| `Shift+N` | Jump to the previous visible changed path |
| `d` | Open a content diff for the selected changed file |
| `/` | Focus the path search input |
| `Ctrl+L` | Clear path and change-kind filters |
| `1` | Toggle added paths |
| `2` | Toggle removed paths |
| `3` | Toggle modified paths |
| `4` | Toggle mode-only paths |

## Daily Backup Screen

Press `b` from the home screen to open the daily backup screen.

### Controls

- **Repository selector** — choose which managed repository to back up.
- **Sync to S3 toggle** — enable or disable the final S3 sync step. Automatically disabled in offline mode.
- **Start Backup** — begins the daily workflow (`create` → `prune` → `compact` → optional `sync`).
- **Clear Log** — clears the log output and resets the progress bar. Available after a backup finishes.

### Progress Bar

The progress bar advances gradually through each stage rather than jumping when a stage finishes. Stage progress within a step is estimated from elapsed wall-clock time against predicted durations.

Progress estimation improves over time because BorgBoi records successful stage durations in the local SQLite database and uses recent timing history to weight each stage more accurately for future runs. If no history is available yet, BorgBoi falls back to built-in default estimates.

See [SQLite Database](sqlite-database.md) for the `backup_stage_timings` table details.

### Daily Backup Keys

| Key | Action |
| --- | --- |
| `Esc` | Return to the home screen (disabled while a backup is running) |

## Excludes Viewer

Press `e` from the home screen to open the excludes viewer.

The first tab shows the shared default excludes file. Each additional tab maps to a managed repository and points at that repo's repo-specific excludes file.

### File Resolution

- Shared default: `~/.borgboi/excludes.txt` by default
- Repo-specific: `~/.borgboi/{repo-name}_excludes.txt` by default

If a repo-specific file does not exist, BorgBoi shows that the repo currently falls back to the shared default excludes file.

### Excludes-Viewer Keys

| Key | Action |
| --- | --- |
| Left / Right | Switch tabs |
| `Ctrl+E` | Enter or leave edit mode |
| `Ctrl+S` | Save the active file |
| `Esc` | Cancel editing or go back |
| `e` | Go back when not editing |

Edits write directly to disk. If you open a missing excludes file in edit mode and save it, BorgBoi creates the file for you.

!!! note "Unsaved edits"
    Pressing `Esc` while editing cancels your unsaved changes. Switching tabs also exits edit mode and restores the selected file from disk.

!!! tip "Exclude syntax help"
    The excludes viewer includes a clickable link to the official Borg exclude-pattern help page.
