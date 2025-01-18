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
