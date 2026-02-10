# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BorgBoi is a Python CLI wrapper around Borg backup tool that automates backup operations with AWS S3 integration and offline mode support. It manages Borg repositories, syncs backups to S3, and tracks repository metadata using DynamoDB or SQLite.

## Development Commands

### Testing
```bash
# Run all tests
just test

# Run tests with coverage report
just test-cov

# Run single test file
uv run pytest tests/specific_test.py -v
```

### Code Quality
```bash
# Run all linters (ruff, mypy, ty, terraform)
just lint

# Format code
just fmt

# Run only ruff checks and formatting
just ruff

# Run only mypy type checking
just mypy

# Run ty type checker
just ty
```

### Build & Installation
```bash
# Install in development mode with all dependency groups
uv sync

# Build package
uv build

# Install package locally
uv pip install -e .
```

### Documentation
```bash
# Serve documentation locally
just serve-docs
```

## Architecture

### Project Structure

```
src/borgboi/
├── cli.py                    # Click-based CLI entry point
├── config.py                 # Pydantic-based configuration with YAML support
├── models.py                 # Core domain models (Repository, BorgBoiRepo)
├── core/
│   ├── orchestrator.py       # Main business logic coordinator
│   ├── models.py             # Operation models (BackupOptions, RetentionPolicy, etc.)
│   ├── errors.py             # Custom exception hierarchy
│   └── output.py             # Output handler abstraction
├── clients/
│   ├── borg_client.py        # Class-based Borg client (new)
│   ├── borg.py               # Legacy Borg functions (being phased out)
│   ├── s3_client.py          # S3 operations abstraction
│   └── utils/                # Shared client utilities
├── storage/
│   ├── base.py               # Abstract RepositoryStorage interface
│   ├── sqlite.py             # SQLite storage backend (offline mode)
│   ├── dynamodb.py           # DynamoDB storage backend (cloud mode)
│   └── migration.py          # Storage migration utilities
└── lib/
    └── passphrase.py         # Passphrase management utilities
```

### Core Components

- **Orchestrator (`core/orchestrator.py`)**: Main business logic coordinator using dependency injection
  - Accepts optional `BorgClient`, `RepositoryStorage`, `S3ClientInterface`, `Config`, and `OutputHandler`
  - Provides high-level operations: `create_repo()`, `backup()`, `daily_backup()`, `restore_archive()`, etc.
  - Handles passphrase resolution and storage backend selection

- **Storage Backends (`storage/`)**: Abstract interface with multiple implementations
  - `RepositoryStorage` base class defines CRUD operations
  - `SQLiteStorage` for offline mode (local SQLite database)
  - `DynamoDBStorage` for cloud mode (AWS DynamoDB)
  - Storage selection is automatic based on `config.offline` flag

- **BorgClient (`clients/borg_client.py`)**: Modern class-based interface to Borg
  - Supports dependency injection for configuration and output handling
  - Returns typed models (`RepoInfo`, `RepoArchive`, `ArchivedFile`)
  - Uses generators for streaming Borg output

- **Configuration (`config.py`)**: Pydantic-based with multiple sources
  - Loads from `~/.borgboi/config.yaml`
  - Environment variable overrides with `BORGBOI_` prefix
  - Nested config uses double underscores (e.g., `BORGBOI_AWS__S3_BUCKET`)
  - Respects `SUDO_USER` for home directory resolution

### Key Features

- **Dual Mode Operation**: Cloud mode (AWS S3 + DynamoDB) and offline mode (SQLite only)
- **Passphrase Management**: File-based storage in `~/.borgboi/passphrases/{repo-name}.key`
  - Migration support from legacy database-stored passphrases
  - Passphrase resolution priority: CLI arg → file → DB (legacy) → env var → config
- **Cross-Platform Support**: Handles Linux/Darwin path differences via `safe_path` computed field
- **Dependency Injection**: Core components accept dependencies for testability

### Important Environment Variables

- `BORGBOI_OFFLINE`: Enable offline mode (uses SQLite instead of DynamoDB)
- `BORGBOI_HOME`: Override home directory for config and passphrases
- `BORGBOI_AWS__S3_BUCKET`: Override S3 bucket name
- `BORGBOI_BORG__COMPRESSION`: Override Borg compression (e.g., `zstd,6`)
- `BORG_NEW_PASSPHRASE`: Passphrase for creating new repositories (fallback)
- `BORG_PASSPHRASE`: Passphrase for existing repositories (fallback)

### CLI Commands

Main commands available via `borgboi` or `bb`:
- `create-repo`: Initialize new Borg repository
- `daily-backup`: Create archive, prune, compact, and optionally sync to S3
- `list-repos`: List all managed repositories
- `list-archives`: List archives in a repository
- `list-archive-contents`: List files in a specific archive
- `get-repo`: Get repository info by name or path
- `repo-info`: Display detailed Borg repository information
- `extract-archive`: Restore archive to current directory
- `delete-archive`: Delete specific archive from repository
- `delete-repo`: Remove repository and metadata
- `restore-repo`: Download repository from S3
- `export-repo-key`: Export repository encryption key
- `create-exclusions`: Create exclusions file from source
- `append-excludes`: Add exclusion pattern to repository
- `modify-excludes`: Remove line from exclusions file
- `migrate-passphrases`: Migrate passphrases from DB to file storage

### Testing Configuration

- Uses pytest with these key settings:
  - `--disable-socket` to prevent network access
  - `--allow-unix-socket` for local services
  - `--import-mode=importlib` for proper module imports
  - Coverage reporting on `src/borgboi`
- Mocks AWS services with moto library
- Test data in `tests/data/` directory
- Cleans up test artifacts (e.g., `private/` directory) after runs

### Infrastructure

- Terraform/OpenTofu configuration in `terraform/` directory
- Manages AWS resources: S3 bucket, DynamoDB tables (repos and archives), IAM policies
- Linting with tflint via `just tflint`
- Validation with `tofu validate` via `just tofu-validate`

## Search Guidance

- Use `ast-grep` for searching and matching source code patterns (AST-aware queries).
- Use `ripgrep` (`rg`) for other text search (docs, configs, logs, and general regex/literal grep).
