# BorgBoi 👦🏼

Wrapper around [Borg](https://borgbackup.readthedocs.io/en/stable/index.html) to ease the process of taking automated backups for my personal systems.

The Borg repository can be synced with an S3 bucket as part of the daily backup operation, or used in offline mode without cloud services.

<img src="docs/images/borgboi_logo.svg" alt="drawing" width="400"/>

## Usage

The program can be invoked with: `borgboi <cmd>` or `bb <cmd>`

### Take Daily Backup

```bash
borgboi daily-backup <path-to-repo>
```

### Offline Mode

BorgBoi supports offline mode for users who prefer not to use AWS services:

```bash
# Enable offline mode with environment variable
export BORGBOI_OFFLINE=1
bb create-repo --repo-path /opt/borg-repos/docs --backup-target ~/Documents

# Or use the --offline flag
bb daily-backup --repo-path /opt/borg-repos/docs --offline
```

## Configuration

BorgBoi uses Dynaconf to load settings from YAML files, environment variables, and `.env` files, and Pydantic models for validation and defaults.

- **Config file:** `~/.borgboi/config.yaml` (Dynaconf loads `config.yaml` from the settings directory).
- **Environment variables:** Use the `BORGBOI` prefix. Nested keys use double underscores (for example: `BORGBOI_BORG__COMPRESSION="zstd,3"` or `BORGBOI_AWS__S3_BUCKET="my-bucket"`).
- **Home dir override:** Set `BORGBOI_HOME` to change the base directory used for config and repo paths.
- **Sudo behavior:** When running with `sudo`, the `SUDO_USER` environment variable is used to resolve the original user's home directory so config and repo paths point to the correct user.
- **Accessing config in code:** Import the singleton `config` or call `get_config()` from `borgboi.config`.

```

## To Do

- [x] Wrap common borg operations for creating archive, pruning, and compacting
- [x] Display borg logs to user through terminal as borg is running
- [x] Sync local borg repo/its archives with a S3 bucket
- [x] Add command to print out information on the borg repo
- [x] Document additional commands
- [x] Add command to delete borg repo
- [x] Add command to download remote borg repo from S3
- [x] Add command to restore from borg repo
- [x] Additional tests
