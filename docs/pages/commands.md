# BorgBoi Commands

!!! info "CLI Structure"
    BorgBoi uses a hierarchical CLI with subcommand groups: `repo`, `backup`, `s3`, `exclusions`, and `config`. Legacy flat commands (like `create-repo`, `daily-backup`) are still available for backward compatibility.

!!! info "Offline Mode"
    All commands support an `--offline` flag (or `BORGBOI_OFFLINE` environment variable) that enables offline mode. In offline mode, BorgBoi stores repository metadata locally in `~/.borgboi/.borgboi_metadata/` instead of using AWS DynamoDB and S3 services.

---

## Repository Commands (`repo`)

### `repo create`

```text
Usage: bb repo create [OPTIONS]

  Create a new Borg repository.

Options:
  -p, --path PATH           Path to create repository  [required]
  -b, --backup-target PATH  Directory to back up  [required]
  -n, --name TEXT           Repository name  [required]
  --passphrase TEXT         Passphrase (auto-generated if not provided)

```

### `repo list`

```text
Usage: bb repo list [OPTIONS]

  List all BorgBoi repositories.

```

!!! warning "Offline Mode Limitation"
    The `repo list` command is not yet implemented in offline mode. Use `repo info` to access individual repositories by name or path in offline mode.

### `repo info`

```text
Usage: bb repo info [OPTIONS]

  Show repository information.

Options:
  -p, --path PATH      Repository path
  -n, --name TEXT      Repository name
  --passphrase TEXT    Passphrase override
  --raw                Show raw Borg output instead of formatted

```

### `repo delete`

```text
Usage: bb repo delete [OPTIONS]

  Delete a Borg repository.

Options:
  -p, --path PATH      Repository path
  -n, --name TEXT      Repository name
  --dry-run            Simulate deletion without making changes
  --passphrase TEXT    Passphrase override
  --delete-from-s3     Also delete from S3

```

---

## Backup Commands (`backup`)

### `backup run`

```text
Usage: bb backup run [OPTIONS]

  Create a new backup archive.

Options:
  -p, --path PATH      Repository path
  -n, --name TEXT      Repository name
  --passphrase TEXT    Passphrase override

```

### `backup daily`

```text
Usage: bb backup daily [OPTIONS]

  Perform daily backup with prune and compact.

Options:
  -p, --path PATH      Repository path  [required]
  --passphrase TEXT    Passphrase override
  --no-s3-sync         Skip S3 sync after backup

```

### `backup list`

```text
Usage: bb backup list [OPTIONS]

  List archives in a repository.

Options:
  -p, --path PATH      Repository path
  -n, --name TEXT      Repository name
  --passphrase TEXT    Passphrase override

```

### `backup contents`

```text
Usage: bb backup contents [OPTIONS]

  List contents of an archive.

Options:
  -p, --path PATH      Repository path
  -n, --name TEXT      Repository name
  -a, --archive TEXT   Archive name  [required]
  -o, --output TEXT    Output file path or 'stdout'  [default: stdout]
  --passphrase TEXT    Passphrase override

```

### `backup restore`

```text
Usage: bb backup restore [OPTIONS]

  Restore an archive to the current directory.

Options:
  -p, --path PATH      Repository path  [required]
  -a, --archive TEXT   Archive name to restore  [required]
  --passphrase TEXT    Passphrase override

```

### `backup delete`

```text
Usage: bb backup delete [OPTIONS]

  Delete an archive from a repository.

Options:
  -p, --path PATH      Repository path  [required]
  -a, --archive TEXT   Archive name to delete  [required]
  --dry-run            Simulate deletion without making changes
  --passphrase TEXT    Passphrase override

```

---

## S3 Commands (`s3`)

### `s3 sync`

```text
Usage: bb s3 sync [OPTIONS]

  Sync a repository to S3.

Options:
  -p, --path PATH      Repository path
  -n, --name TEXT      Repository name

```

### `s3 restore`

```text
Usage: bb s3 restore [OPTIONS]

  Restore a repository from S3.

Options:
  -p, --path PATH      Repository path
  -n, --name TEXT      Repository name
  --dry-run            Simulate restoration without making changes
  --force              Force restore even if repository exists locally

```

### `s3 delete`

```text
Usage: bb s3 delete [OPTIONS]

  Delete a repository from S3.

Options:
  -n, --name TEXT      Repository name  [required]
  --dry-run            Simulate deletion without making changes

```

### `s3 stats`

```text
Usage: bb s3 stats

  Show general S3 bucket storage metrics and class composition.

  Displays total bucket size, total object count, and a storage class breakdown
  including Intelligent-Tiering tiers (FA/IA/AIA/AA/DAA) when available.
  Values are sourced from AWS/S3 CloudWatch daily storage metrics.

```

---

## Exclusions Commands (`exclusions`)

### `exclusions create`

```text
Usage: bb exclusions create [OPTIONS]

  Create an exclusions file for a repository.

Options:
  -p, --path PATH      Repository path  [required]
  -s, --source FILE    Source file with exclusion patterns  [required]

```

### `exclusions show`

```text
Usage: bb exclusions show [OPTIONS]

  Show exclusion patterns for a repository.

Options:
  -n, --name TEXT      Repository name  [required]

```

### `exclusions add`

```text
Usage: bb exclusions add [OPTIONS]

  Add an exclusion pattern to a repository.

Options:
  -n, --name TEXT      Repository name  [required]
  -x, --pattern TEXT   Exclusion pattern to add  [required]

```

### `exclusions remove`

```text
Usage: bb exclusions remove [OPTIONS]

  Remove an exclusion pattern by line number.

Options:
  -n, --name TEXT      Repository name  [required]
  -l, --line INTEGER   Line number to remove (1-based)  [required]

```

---

## Configuration Commands (`config`)

### `config show`

```text
Usage: bb config show [OPTIONS]

  Display the current BorgBoi configuration.

Options:
  -p, --path PATH           Custom path for the configuration file
  -f, --format [yaml|json|tree]
                            Output format  [default: yaml]
  --pretty-print/--no-pretty-print
                            Pretty print output using rich  [default: pretty-print]

```

---

## Utility Commands

### `migrate-passphrases`

```text
Usage: bb migrate-passphrases [OPTIONS]

  Migrate repository passphrases from database to secure file storage.

  Passphrases are migrated to ~/.borgboi/passphrases/{repo-name}.key
  with 0o600 permissions.

Options:
  -n, --repo-name TEXT   Specific repo to migrate (migrates all if omitted)
  --offline              Enable offline mode (no AWS services)

```

---

## Legacy Commands

!!! note "Backward Compatibility"
    The following legacy commands are still available for backward compatibility but are deprecated. Consider using the new hierarchical commands above.

| Legacy Command | New Command |
|----------------|-------------|
| `create-repo` | `repo create` |
| `list-repos` | `repo list` |
| `get-repo` | `repo info` |
| `repo-info` | `repo info` |
| `delete-repo` | `repo delete` |
| `daily-backup` | `backup daily` |
| `list-archives` | `backup list` |
| `list-archive-contents` | `backup contents` |
| `extract-archive` | `backup restore` |
| `delete-archive` | `backup delete` |
| `restore-repo` | `s3 restore` |
| `create-exclusions` | `exclusions create` |
| `append-excludes` | `exclusions add` |
| `modify-excludes` | `exclusions remove` |
| `export-repo-key` | *(no new equivalent)* |
