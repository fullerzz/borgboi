# BorgBoi V2 Refactor Plan (inspired by borgopher)

## Goals
- Modernize the Python CLI architecture using proven patterns from borgopher.
- Increase reliability around passphrases, offline mode, and AWS/S3 interactions.
- Improve testability and performance for large repositories.
- Align domain models, validation, and output handling across the stack.

## Deep-Dive Summary: borgopher (Go)

### Key Patterns
- **Orchestrator as the single integration point**: `core.Orchestrator` composes config, validation, borg client, offline storage, and AWS clients. It centralizes workflows (backup, prune, compact, sync, delete).
- **Explicit domain models**: `core.models` defines Repository, Archive, RepoInfo, RetentionPolicy, BackupOptions, RestoreOptions, etc, with clear JSON tags and optional fields.
- **Validator with rich semantic rules**: field-level validation for names, paths, retention, compression formats, and exclusion patterns.
- **Command execution with structured output handlers**: Borg client supports stdout/stderr/progress/JSON callbacks; warning vs fatal errors are differentiated.
- **Offline storage as a first-class capability**: centralized JSON storage with read/write locks, exclusions management, and cached S3 stats.
- **Config layering & defaults**: defaults are explicit; config file + env overrides; validation occurs after load.
- **Passphrase handling**: file-based storage with strict permissions and resolution priorities (file > env), explicitly separated for new repo creation vs ongoing usage.
- **Resilient workflows**: workflows treat Borg warning exit codes as non-fatal and continue steps; also attempt metadata persistence even if AWS fails.
- **Structured S3 interactions**: wrappers around AWS SDK + s3 stats cache for performance.
- **CLI command hierarchy**: `repo` and `s3` subcommands, while preserving legacy commands for compatibility.

### borgopher Data Structures Worth Mirroring
- `Repository` (metadata + passphrase file path + retention override)
- `RepoInfo`, `CacheInfo`, `RepositoryInfo`
- `Archive`, `ArchiveStats`
- `BackupOptions`, `RestoreOptions`, `RetentionPolicy`
- `Borg Error` type with exit code classification and warning/fatal helpers

### What borgopher does well
- Strong orchestration boundaries and dependency injection.
- Centralized validation and config enforcement.
- A single Borg client for all process execution and output parsing.
- Offline storage is robust and supports listing/searching.
- AWS interactions are abstracted and testable via interfaces.
- Better operational feedback (warnings vs failures, progress handlers).

### Potential Improvement Areas in borgopher
- Passphrase handling in env is still used during operations (though controlled); more explicit lifecycle guards could help.
- Some functions are very large; could be broken into sub-workflows or helpers for clarity.
- Offline storage uses JSON; could evolve to a richer local store or add indexing for large datasets.

## Deep-Dive Summary: borgboi (Python)

### Current Patterns
- Orchestrator functions are procedural and shared directly with CLI commands.
- Domain models exist (`BorgBoiRepo`, `RepoInfo`, etc) but are less formalized around operations (e.g., backup options, retention policy).
- Validation is split (some in `validator.py`, some in `orchestrator.py`, some in clients).
- Borg client uses subprocess directly and yields stderr lines; no structured output handler or error classification.
- Offline storage uses per-repo JSON files, with limited listing/lookup capability.
- S3 operations use AWS CLI commands directly with stdout streaming.
- Config handled via dynaconf + pydantic (strong baseline), but validation is minimal.

### Gaps vs borgopher
- No centralized workflow manager that fully encapsulates Borg + AWS interactions.
- No structured error classification or warning handling.
- Offline storage lacks indexing / listing.
- Validation is not enforced for critical fields (archive name, compression, paths).
- No consistent passphrase lifecycle enforcement (CLI, env, file precedence varies).
- Limited resiliency and rollback behavior for multi-step operations.

## V2 Refactor Plan

### 1) Core Architecture
- **Introduce a `core` package** similar to borgopher:
  - `core/orchestrator.py`: single entry point for workflows.
  - `core/models.py`: domain models for Repository, Archive, RepoInfo, BackupOptions, RestoreOptions, RetentionPolicy.
  - `core/validator.py`: centralized validation with explicit rules.
- **Inject dependencies** (borg client, offline storage, aws client) into orchestrator for testability.

### 2) Borg Client Modernization
- **Create a Borg client class** in `clients/borg_client.py` that:
  - Defines `BorgError` with exit code classification (warning vs fatal).
  - Supports `OutputHandler` callbacks (stdout/stderr/progress/json).
  - Provides a uniform command builder for Borg operations (init, create, prune, compact, check, diff, recreate, info, list, extract, delete).
- **Adopt JSON parsing for info/list operations** and isolate parsing logic.

### 3) Offline Storage Redesign
- **Create a single JSON index file** (e.g., `~/.borgboi/data/repositories.json`) for fast listing/lookup.
- Move exclusions to `~/.borgboi/data/exclusions/{repo}.txt`.
- Add an **S3 stats cache** file (like borgopher) to avoid expensive calls.
- Provide thread-safe read/write semantics (locks) for concurrent operations.

### 4) Passphrase Lifecycle Enforcement
- **Adopt borgopher’s file-first policy** and limit environment fallback to repo creation.
- Separate resolution paths:
  - `resolve_new_repo_passphrase()` for repo creation (CLI > file > env > config > generated).
  - `resolve_existing_repo_passphrase()` for operations (CLI > file > legacy DB > config; env only with explicit flag).
- Enforce strict file permission checks and auto-fix warnings.

### 5) Workflow Improvements
- **Implement workflow methods on orchestrator**:
  - `create_repo`, `backup_repo`, `daily_backup`, `sync_repo`, `restore_repo`, `delete_repo`, `archive_info`, `diff_archives`, `recreate_archive`.
- Use structured warning handling: treat Borg exit code 1 as warnings (continue) and surface summary.
- Track last backup and last S3 sync timestamps consistently in storage.
- Introduce **retention overrides per repo** and a standard fallback policy (config > defaults).

### 6) CLI Structure and UX
- Move from flat Click commands to a **hierarchical CLI**:
  - `repo create`, `repo list`, `repo info`, `repo move`, `repo delete`, `repo exclusions`.
  - `backup run`, `backup list`, `backup restore`, `backup diff`, `backup recreate`.
  - `s3 sync`, `s3 stats`, `s3 delete`.
- Keep legacy commands as deprecated aliases (to avoid breaking users).
- Centralize output formatting and status messaging.

### 7) Config Validation and Defaults
- Add a `config.validate()` phase similar to borgopher:
  - Borg executable exists or is found in PATH.
  - AWS config required only when offline = false.
  - Validate compression format and retention ranges.

### 8) AWS and S3 Client Improvements
- Wrap AWS interactions into a dedicated client class (`clients/aws_client.py`).
- Provide testable interfaces for DynamoDB and S3 operations (moto test support).
- Cache S3 stats locally to avoid repeated listing operations.

### 9) Testing Plan
- Add unit tests for validator, passphrase resolution, and retention policy.
- Add integration tests for orchestrator workflows (mock Borg and AWS).
- Use fixtures to simulate repositories and offline storage.

### 10) Migration Strategy
- **Phase 1:** Introduce new core modules while keeping existing CLI behavior.
- **Phase 2:** Migrate CLI commands to the new orchestrator APIs.
- **Phase 3:** Replace old offline storage with new indexed JSON store (with migration script).
- **Phase 4:** Deprecate legacy paths in a major release.

## Big Ideas / Optional Sweeping Changes
- **Move to a clean architecture layout** (`core`, `clients`, `storage`, `cli`, `models`).
- **Introduce structured event logging** (JSON logs with levels and structured context for workflows).
- **Add execution telemetry** (duration, exit codes, warnings) for each operation.
- **Pluggable storage layer** (JSON now, SQLite later) to enable advanced queries.
- **Native Borg progress parsing** for consistent progress reporting with Rich.

## High-Level Deliverables
- `core/orchestrator.py` and `core/models.py` (new).
- `clients/borg_client.py` with structured error handling.
- `storage/offline.py` with indexed JSON metadata and exclusions management.
- Updated CLI command hierarchy using Click groups.
- Migration utilities for passphrases and offline metadata.

---

This plan captures borgopher’s strongest ideas (orchestrator-centric design, explicit models, validation, structured execution) and outlines how borgboi can evolve into a more robust, scalable V2 architecture.
