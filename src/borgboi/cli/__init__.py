"""Hierarchical CLI for BorgBoi.

This module provides a restructured CLI with subcommands organized
by function: repo, backup, s3, exclusions.
"""

from borgboi.cli.main import app, cli, main

__all__ = ["app", "cli", "main"]
