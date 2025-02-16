## v0.11.0 (2025-02-16)

### Feat

- **delete-archive**: add CLI command to delete individual archives from within borg repo
- **delete-archive**: add support for deleting individual archives from borg repositories

### Fix

- **delete-repo**: don't call 'compact' command if entire repo is deleted
- **delete-op**: run compact command on repo after deletion command
- **delete-op**: deletion confirmation prompt now accepts repo name and archive name as params
- **delete-repo**: Repo is now delete from DynamoDB table after successful local removal

## v0.10.0 (2025-02-15)

### Feat

- add command to delete borg repo and preview deletion with dry-run

### Refactor

- raise ValueError instead of exit(0)

## v0.9.0 (2025-02-09)

### BREAKING CHANGE

- Updated type of both path and backup_target fields in BorgRepo from Path to str
- The new field os_platform needs to be manually inserted into each item that already exists in the DynamoDB table.

### Feat

- add new field 'os_platform' to BorgRepo

### Fix

- refactor validation of repo and backup target paths to resolve issue with remote repos

## v0.8.0 (2025-02-01)

### BREAKING CHANGE

- An exclusion file must exist before a daily backup or archive can be created. There is a new borgboi command to create this exclusions list. After it's created, it will be persisted. Closes #21

### Feat

- add ability to create exclusion list for each borg repo

### Fix

- **orchestrator**: the borgboi dir will be created if it doesn't exist before attempting to create exlusions file

## v0.7.0 (2025-01-31)

### Feat

- **list-repos**: add deduplicated repo size to output

### Refactor

- **dynamodb**: add botocore config to set retry behavior mode to 'standard'

## v0.6.1 (2025-01-26)

### Refactor

- **repo-info**: improved pretty print output for the borgboi repo-info command

## v0.6.0 (2025-01-25)

### Feat

- **repo-info**: add pretty print flag to repo info command

## v0.5.0 (2025-01-25)

### Feat

- implement command to extract borg archive

## v0.4.0 (2025-01-22)

### Feat

- now store repo size metadata in dynamodb table
- improved repo-info command and added data structure to store output

### Refactor

- moved borg repo info models and cmd execution into backups.py

## v0.3.0 (2025-01-18)

### Feat

- add new command to view borg repo info

### Refactor

- move get repo info logic into orchestrator and added validator module

## v0.2.2 (2025-01-18)

### Refactor

- renamed dynamo table item field from name to common_name

## v0.2.1 (2025-01-18)

### Fix

- **s3**: adds s3 prefix of borg repo name before syncing with s3

## v0.2.0 (2025-01-18)

### Feat

- add cmd to export repo key in addition to automatically exporting repo key upon repo creation

## v0.1.0 (2025-01-17)

### Feat

- **list-repos**: improved appearance of table output
- added command to init repo and added additional metadata to classes
- added cli commands for borg create archive, borg prune, and borg compact

### Fix

- list repos command no longer errors out due to the presence of remote repos in the response

### Refactor

- **list-repos**: added additional columns with last sync time to table output and moved logic into orchestrator
- 'daily-backup' command now creates archive, runs prune, and runs compact
