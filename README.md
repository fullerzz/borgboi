# BorgBoi 👦🏼

Wrapper around [Borg](https://borgbackup.readthedocs.io/en/stable/index.html) to ease the process of taking automated backups for my personal systems.

The Borg repository is synced with an S3 bucket as part of the daily backup operation.

## Usage

The program can be invoked with: `borgboi <cmd>` or `bb <cmd>`

### Take Daily Backup

```bash
borgboi daily-backup <path-to-repo>
```

## To Do

- [x] Wrap common borg operations for creating archive, pruning, and compacting
- [x] Display borg logs to user through terminal as borg is running
- [x] Sync local borg repo/its archives with a S3 bucket
- [x] Add command to print out information on the borg repo
- [ ] Document additional commands
- [x] Add command to delete borg repo
- [x] Add command to download remote borg repo from S3
- [x] Add command to restore from borg repo
- [x] Additional tests
