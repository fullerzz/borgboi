# BorgBoi Commands

!!! info "CLI Structure"
    BorgBoi uses a Cyclopts-powered CLI with subcommand groups: `repo`, `backup`, `s3`, `exclusions`, `config`, plus root commands including `tui` and `version`.

!!! info "Offline Mode"
    All commands support root-level `--offline` and `--debug` flags. `--offline` can also be enabled with `BORGBOI_OFFLINE`. In offline mode, BorgBoi stores repository metadata locally in `~/.borgboi/.database/borgboi.db` instead of using AWS DynamoDB and S3 services.

!!! tip "Use generated help"
    Run `bb --help` or `bb <group> <command> --help` to view the current help output generated directly from the Cyclopts app.

---

## Root Commands

### `tui`

Launch the interactive Textual TUI.

- Optional: `--offline`, `--debug`

```sh
bb tui
```

The home screen shows a repository table and a 14-day archive activity sparkline.

Home-screen keys:

- `q`: quit the app
- `r`: refresh the repository list and sparkline
- `c`: open the config viewer screen
- `e`: open the excludes viewer
- `b`: open the daily backup screen

See [TUI](tui.md) for full details on the config viewer, daily backup screen, and excludes viewer.

### `version`

Print the installed BorgBoi version.

```sh
bb version
```

---

## Repository Commands (`repo`)

### `repo create`

Create a new Borg repository.

- Required: `--path/-p`, `--backup-target/-b`, `--name/-n`
- Optional: `--passphrase`

```sh
bb repo create --path /opt/borg-repos/docs \
    --backup-target ~/Documents \
    --name my-docs-backup
```

### `repo import`

Register an existing Borg repository with BorgBoi.

- Required: `--path/-p`, `--backup-target/-b`, `--name/-n`
- Optional: `--passphrase`

```sh
bb repo import --path /opt/borg-repos/docs \
    --backup-target ~/Documents \
    --name my-docs-backup
```

This command validates the existing repository with `borg info`, stores the passphrase in BorgBoi's secure passphrase directory when one is available, and writes the repository metadata without reinitializing the repo.

### `repo list`

List all BorgBoi repositories.

### `repo info`

Show repository information.

- Target the repository with `--name/-n` or `--path/-p`
- Optional: `--passphrase`, `--raw`

`--raw` prints Borg's raw repository info output instead of BorgBoi's formatted summary.

### `repo delete`

Delete a Borg repository.

- Target the repository with `--name/-n` or `--path/-p`
- Optional: `--dry-run`, `--passphrase`, `--delete-from-s3`
- Prompts for confirmation unless `--dry-run` is used

---

## Backup Commands (`backup`)

### `backup run`

Create a new backup archive.

- Target the repository with `--name/-n` or `--path/-p`
- Optional: `--passphrase`, `--no-json`

By default, BorgBoi uses Borg JSON logging so it can render a post-backup summary table. `--no-json` disables that and streams Borg's native output instead.

!!! info "Exclude File Resolution"
    Backup commands (`backup run` and `backup daily`) resolve exclusion files in this order:

    1. `~/.borgboi/{repo-name}_excludes.txt` (repository-specific)
    2. `~/.borgboi/excludes.txt` (shared default)

    If neither file exists, backup fails with: `Exclude list must be created before performing a backup`.

### `backup daily`

Perform the daily workflow: create an archive, prune old archives, compact the repo, and sync to S3.

- Requires exactly one of `--name/-n` or `--path/-p`
- Optional: `--passphrase`, `--no-s3-sync`

`--no-s3-sync` keeps the local backup workflow but skips the final S3 sync step.

### `backup list`

List archives in a repository.

- Target the repository with `--name/-n` or `--path/-p`
- Optional: `--passphrase`

Archives are shown newest-first.

### `backup contents`

List contents of an archive.

- Required: `--archive/-a`
- Target the repository with `--name/-n` or `--path/-p`
- Optional: `--output/-o` (defaults to `stdout`), `--passphrase`

When `--output` points to a file, BorgBoi writes the archive paths there instead of printing them.

### `backup restore`

Restore an archive into the current working directory.

- Required: `--path/-p`, `--archive/-a`
- Optional: `--passphrase`
- Prompts for confirmation before extraction

### `backup delete`

Delete an archive from a repository.

- Required: `--path/-p`, `--archive/-a`
- Optional: `--dry-run`, `--passphrase`
- Prompts for confirmation unless `--dry-run` is used

---

## S3 Commands (`s3`)

### `s3 sync`

Sync a repository to S3.

- Target the repository with `--name/-n` or `--path/-p`

### `s3 restore`

Restore a repository from S3.

- Target the repository with `--name/-n` or `--path/-p`
- Optional: `--dry-run`, `--force`

### `s3 delete`

Delete a repository from S3.

- Required: `--name/-n`
- Optional: `--dry-run`
- Prompts for confirmation unless `--dry-run` is used

!!! warning "Current status"
    The command is present in the CLI surface, but the Cyclopts migration kept it as a placeholder and it currently prints `S3 delete for '<name>' not yet implemented (dry_run=<bool>)`.

### `s3 stats`

Show general S3 bucket storage metrics and class composition.

The output includes total bucket size, total object count, storage class breakdown, and Intelligent-Tiering transition estimates when S3 Inventory data is available.

---

## Exclusions Commands (`exclusions`)

### `exclusions create`

Create an exclusions file for a repository.

- Required: `--path/-p`, `--source/-s`

### `exclusions show`

Show exclusion patterns for a repository.

- Required: `--name/-n`

The command prefers a repository-specific exclusions file and falls back to the shared default file when present.

### `exclusions add`

Add an exclusion pattern to a repository.

- Required: `--name/-n`, `--pattern/-x`

### `exclusions remove`

Remove an exclusion pattern by line number.

- Required: `--name/-n`, `--line/-l`

---

## Configuration Commands (`config`)

### `config show`

Display the current BorgBoi configuration.

- Optional: `--path/-p`, `--format/-f {yaml,json,tree}`, `--pretty-print`, `--no-pretty-print`

`tree` renders a Rich tree view. Plain YAML/JSON can be forced with `--no-pretty-print`. When environment variables override config values, BorgBoi highlights those overrides in the tree view and adds `_env_overrides` to JSON output.

---
