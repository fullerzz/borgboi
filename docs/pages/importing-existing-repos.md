# Importing Existing Borg Repos

Use `bb repo import` when you already have a Borg repository on disk and want BorgBoi to manage it.

## What `repo import` does

- Verifies the repository path already exists and is readable by Borg
- Confirms the repository is not already registered with BorgBoi on this host
- Captures repository metadata with `borg info`
- Stores the passphrase in `~/.borgboi/passphrases/{repo-name}.key` when BorgBoi can resolve one
- Saves the repository metadata so the repo appears in `bb repo list` and can be used with backup commands

`repo import` does **not** run `borg init` and does not modify the repository contents.

## Prerequisites

- BorgBackup is installed and available in your shell
- The repository already exists on disk
- The backup target directory you want BorgBoi to use already exists
- You know how BorgBoi should resolve the repo passphrase if the repository is encrypted

## Basic import

```sh
bb repo import --path /opt/borg-repos/docs \
    --backup-target ~/Documents \
    --name my-docs-backup
```

## Passphrase resolution

BorgBoi resolves the passphrase in this order during import:

1. `--passphrase`
2. An existing stored passphrase file for the repo name
3. `BORG_PASSPHRASE` in the shell environment
4. `borg.borg_passphrase` in `~/.borgboi/config.yaml`

For encrypted repositories, make sure one of those sources is available before running the import. If BorgBoi resolves a passphrase successfully, it stores it in `~/.borgboi/passphrases/{repo-name}.key` for future commands.

## Verify the import

After importing, confirm the repo is registered and readable:

```sh
bb repo list
bb repo info --name my-docs-backup
```

If you plan to run backups immediately, also make sure an exclusions file exists:

```sh
bb exclusions create --path /opt/borg-repos/docs --source ~/borgboi-excludes.txt
```

## Common failure cases

### Repository name already exists

Pick a different `--name` or remove the old registration first.

### Repository path is already registered

The repo is already managed by BorgBoi on this host. Use `bb repo list` to inspect the existing registration.

### Borg cannot read the repository

This usually means one of the following:

- the path is not a Borg repository
- the repository is encrypted and no passphrase was provided
- the provided passphrase is incorrect

Try again with `--passphrase` or set the passphrase in your environment/config before importing.

### Backup target path does not exist

Create the directory first, then rerun `bb repo import`.
