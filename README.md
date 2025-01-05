# borgboi 👦🏼

Wrapper around [Borg](https://borgbackup.readthedocs.io/en/stable/index.html) to ease the process of taking automated backups for my personal systems.

## Usage

The program can be invoked with: `borgboi <cmd>` or `bb <cmd>`

### Take Daily Backup

```bash
borgboi daily-backup <path-to-repo>
```

## To Do

- [x] Wrap common borg operations for creating archive, pruning, and compacting
- [ ] Display borg logs to user through terminal as borg is running
- [ ] Add command to print out information on the borg repo
- [ ] Sync local borg repo/its archives with a S3 bucket
