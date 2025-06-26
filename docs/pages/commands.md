# BorgBoi Commands

!!! info "Offline Mode"
    All commands support an `--offline` flag (or `BORGBOI_OFFLINE` environment variable) that enables offline mode. In offline mode, BorgBoi stores repository metadata locally in `~/.borgboi/.borgboi_metadata/` instead of using AWS DynamoDB and S3 services.

## `create-repo`

```text
Usage: borgboi create-repo [OPTIONS]

  Create a new Borg repository.

Options:
  -r, --repo-path PATH      [required]
  -b, --backup-target PATH  [required]
  --offline                 Enable offline mode (no AWS services)

```

## `create-exclusions`

```text
Usage: bb create-exclusions [OPTIONS]

  Create a new exclusions list for a Borg repository.

Options:
  -r, --repo-path PATH          [required]
  -x, --exclusions-source FILE  [required]
  --offline                     Enable offline mode (no AWS services)

```

## `append-excludes`

```text
Usage: bb append-excludes [OPTIONS]

  Append a new exclusion pattern to the repository.

Options:
  -n, --repo-name TEXT          Name of the repository  [required]
  -x, --exclusion-pattern TEXT  Exclusion pattern to add  [required]
  --offline                     Enable offline mode (no AWS services)

```

## `modify-excludes`

```text
Usage: bb modify-excludes [OPTIONS]

  Delete a line from a repository's excludes file.

Options:
  -n, --repo-name TEXT           Name of the repository  [required]
  -D, --delete-line-num INTEGER  Line number to delete  [required]
  --offline                      Enable offline mode (no AWS services)

```

## `list-repos`

```text
Usage: bb list-repos [OPTIONS]

  List all BorgBoi repositories.

Options:
  --offline                 Enable offline mode (no AWS services)

```

!!! warning "Offline Mode Limitation"
    The `list-repos` command is not yet implemented in offline mode. Use `get-repo` to access individual repositories by name or path in offline mode.

## `list-archives`

```text
Usage: bb list-archives [OPTIONS]

  List the archives in a Borg repository.

Options:
  -r, --repo-path PATH
  -n, --repo-name PATH
  --offline                 Enable offline mode (no AWS services)

```

## `list-archive-contents`

```text
Usage: bb list-archive-contents [OPTIONS]

  List the contents of a Borg archive.

Options:
  -r, --repo-path PATH
  -n, --repo-name TEXT
  -a, --archive-name TEXT   [required]
  -o, --output TEXT         Output file path or stdout  [default: stdout]
  --offline                 Enable offline mode (no AWS services)

```

## `get-repo`

```text
Usage: bb get-repo [OPTIONS]

  Get a Borg repository by name or path.

Options:
  -r, --repo-path PATH
  -n, --repo-name PATH
  --offline                 Enable offline mode (no AWS services)

```

## `repo-info`

```text
Usage: bb repo-info [OPTIONS]

  List a local Borg repository's info.

Options:
  -r, --repo-path PATH
  -n, --repo-name TEXT
  --pp / --no-pp            Pretty print the repo info  [default: pp]
  --offline                 Enable offline mode (no AWS services)

```

## `daily-backup`

```text
Usage: bb daily-backup [OPTIONS]

  Create a new archive of the repo's target directory with borg and perform pruning and
  compaction.

Options:
  -r, --repo-path PATH  [required]
  --offline             Enable offline mode (no AWS services)

```

## `extract-archive`

```text
Usage: bb extract-archive [OPTIONS]

  Extract a Borg archive into the current working directory.

Options:
  -r, --repo-path PATH     [required]
  -a, --archive-name TEXT  [required]
  --offline                Enable offline mode (no AWS services)
```

## `export-repo-key`

```text
Usage: bb export-repo-key [OPTIONS]

  Extract the Borg repository's repo key.

Options:
  -r, --repo-path PATH  [required]
  --offline             Enable offline mode (no AWS services)

```

## `delete-archive`

```text
Usage: bb delete-archive [OPTIONS]

  Delete a Borg archive from the repository.

Options:
  -r, --repo-path PATH     [required]
  -a, --archive-name TEXT  [required]
  --dry-run                Perform a dry run of the deletion
  --offline                Enable offline mode (no AWS services)

```

## `delete-repo`

```text
Usage: bb delete-repo [OPTIONS]

  Delete a Borg repository.

Options:
  -r, --repo-path PATH
  -n, --repo-name PATH
  --dry-run             Perform a dry run of the deletion
  --offline             Enable offline mode (no AWS services)

```

## `restore-repo`

```text
Usage: bb restore-repo [OPTIONS]

  Restore a Borg repository by name or path by downloading it from S3.

Options:
  -r, --repo-path PATH
  -n, --repo-name TEXT
  --dry-run                 Perform a dry run of the restore
  --force                   Force restore even if repo exists
  --offline                 Enable offline mode (no AWS services)

```
