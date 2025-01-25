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
