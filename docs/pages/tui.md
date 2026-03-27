# TUI

Use `bb tui` to open BorgBoi's interactive terminal dashboard.

```sh
bb tui
```

The TUI uses the same effective configuration as the CLI, so `--offline`, `--debug`, and `BORGBOI_*` overrides all apply here too.

## Daily Backup Progress

The daily backup screen keeps the existing stage boundaries (`create`, `prune`, `compact`, and optional `sync`), but progress within each stage now advances gradually instead of only jumping when a stage finishes.

Progress estimation improves over time because BorgBoi records successful stage durations in the local SQLite database and uses recent timing history to weight each stage more accurately for future runs. If no history is available yet, BorgBoi falls back to built-in default estimates.

See [SQLite Database](sqlite-database.md) for the `backup_stage_timings` table details.

## Main Screen

When the app starts, BorgBoi loads your managed repositories into a table with these columns:

- `Name`
- `Local Path`
- `Hostname`
- `Last Archive`
- `Size`
- `Backup Target`

You can also toggle a sidebar that shows the effective configuration grouped into `General`, `AWS`, `Borg`, `Retention`, and `UI` sections.

## Main-Screen Keys

| Key | Action |
| --- | --- |
| `q` | Quit the app |
| `r` | Refresh the repository list |
| `c` | Toggle the config sidebar |
| `e` | Open the excludes viewer |

## Excludes Viewer

Press `e` from the main screen to open the excludes viewer.

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
