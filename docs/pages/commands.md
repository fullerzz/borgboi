# BorgBoi Commands

## `create-repo`

```text
Usage: borgboi create-repo [OPTIONS]

  Create a new Borg repository.

Options:
  -r, --repo-path PATH      [required]
  -b, --backup-target PATH  [required]

```

## `create-exclusions`

```text
Usage: bb create-exclusions [OPTIONS]

  Create a new exclusions list for a Borg repository.

Options:
  -r, --repo-path PATH          [required]
  -x, --exclusions-source FILE  [required]

```

## `list-repos`

```text
Usage: bb list-repos [OPTIONS]

  List all BorgBoi repositories.

```

## `list-archives`

```text
Usage: bb list-archives [OPTIONS]

  List the archives in a Borg repository.

Options:
  -r, --repo-path PATH
  -n, --repo-name PATH

```

## `get-repo`

```text
Usage: bb get-repo [OPTIONS]

  Get a Borg repository by name or path.

Options:
  -r, --repo-path PATH
  -n, --repo-name PATH

```

## `daily-backup`

```text
Usage: bb daily-backup [OPTIONS]

  Create a new archive of the repo's target directory with borg and perform pruning and
  compaction.

Options:
  -r, --repo-path PATH  [required]

```

## `extract-archive`

```text
Usage: bb extract-archive [OPTIONS]

  Extract a Borg archive into the current working directory.

Options:
  -r, --repo-path PATH     [required]
  -a, --archive-name TEXT  [required]
```

## `export-repo-key`

```text
Usage: bb export-repo-key [OPTIONS]

  Extract the Borg repository's repo key.

Options:
  -r, --repo-path PATH  [required]

```

## `delete-archive`

```text
Usage: bb delete-archive [OPTIONS]

  Delete a Borg archive from the repository.

Options:
  -r, --repo-path PATH     [required]
  -a, --archive-name TEXT  [required]
  --dry-run                Perform a dry run of the deletion

```

## `delete-repo`

```text
Usage: bb delete-repo [OPTIONS]

  Delete a Borg repository.

Options:
  -r, --repo-path PATH
  -n, --repo-name PATH
  --dry-run             Perform a dry run of the deletion

```
