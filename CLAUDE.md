# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BorgBoi is a Python CLI wrapper around Borg backup tool that automates backup operations with AWS S3 integration and offline mode support. It manages Borg repositories, syncs backups to S3, and tracks repository metadata using DynamoDB.

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
# Run all linters (ruff, mypy, vulture, terraform)
just lint

# Format code
just fmt

# Run only ruff checks and formatting
just ruff

# Run only mypy type checking
just mypy
```

### Build & Installation
```bash
# Install in development mode
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

### Core Components

- **CLI (`cli.py`)**: Click-based command-line interface with commands for backup operations
- **Orchestrator (`orchestrator.py`)**: Main business logic coordinator that manages repo operations
- **Models (`models.py`)**: Pydantic models for data validation, primarily `BorgBoiRepo`
- **Clients**: Separate client modules for different services:
  - `borg.py`: Borg backup tool wrapper
  - `dynamodb.py`: AWS DynamoDB operations for metadata storage
  - `s3.py`: AWS S3 operations for backup sync
  - `offline_storage.py`: Local storage for offline mode

### Key Features

- **Dual Mode Operation**: Cloud mode (AWS S3 + DynamoDB) and offline mode (local storage only)
- **Environment-Based Configuration**: Uses `BORGBOI_OFFLINE` environment variable
- **Cross-Platform Support**: Handles Linux/Darwin path differences
- **Rich CLI Output**: Uses Rich library for formatted terminal output

### Important Environment Variables

- `BORG_NEW_PASSPHRASE`: Required for creating new Borg repositories
- `BORGBOI_OFFLINE`: Set to enable offline mode (no AWS services)
- `BORGBOI_DIR_NAME`: Directory name for BorgBoi metadata (default: `.borgboi`)

### CLI Commands

Main commands available via `borgboi` or `bb`:
- `create-repo`: Initialize new Borg repository
- `daily-backup`: Perform daily backup operation
- `list-repos`: List all managed repositories
- `restore-repo`: Restore from backup
- `delete-repo`: Remove repository

### Testing Configuration

- Uses pytest with coverage reporting
- Mocks AWS services with moto library
- Disables network sockets during tests
- Test data stored in `tests/data/` directory

### Infrastructure

- Terraform configuration in `terraform/` directory
- Manages AWS resources (S3, DynamoDB, IAM)
- Uses OpenTofu for infrastructure management