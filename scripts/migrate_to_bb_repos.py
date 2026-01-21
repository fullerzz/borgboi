#!/usr/bin/env python3
"""
Migration script to migrate data from borgboi-repos table to bb-repos table.

This script reads all items from the old 'borgboi-repos' DynamoDB table,
transforms them to the new schema (renaming common_name -> repo_name, dropping metadata),
and writes them to the new 'bb-repos' table.

Usage:
    python scripts/migrate_to_bb_repos.py

Environment Variables:
    AWS_REGION: AWS region (default: us-west-2)
    OLD_TABLE_NAME: Source table name (default: borgboi-repos)
    NEW_TABLE_NAME: Destination table name (default: bb-repos)
"""

import os
from typing import Any

import boto3
from botocore.config import Config

boto_config = Config(retries={"mode": "standard"})

OLD_TABLE_NAME = os.environ.get("OLD_TABLE_NAME", "borgboi-repos")
NEW_TABLE_NAME = os.environ.get("NEW_TABLE_NAME", "bb-repos")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")


def transform_item(old_item: dict[str, Any]) -> dict[str, Any]:
    """
    Transform an item from the old schema to the new schema.

    Old schema (BorgRepoTableItem):
        - repo_path (hash key)
        - backup_target_path
        - common_name
        - hostname
        - os_platform
        - last_backup (optional)
        - metadata (optional, complex nested object)

    New schema (BorgBoiRepoItem):
        - repo_path (hash key)
        - hostname (range key)
        - backup_target_path
        - repo_name (renamed from common_name)
        - last_backup (optional)
        - last_s3_sync (optional, new field)
        - os_platform (optional)
        - passphrase (optional, new field)
        - retention_keep_daily (optional, new field)
        - retention_keep_weekly (optional, new field)
        - retention_keep_monthly (optional, new field)
        - retention_keep_yearly (optional, new field)
    """
    new_item: dict[str, Any] = {
        "repo_path": old_item["repo_path"],
        "hostname": old_item["hostname"],
        "backup_target_path": old_item["backup_target_path"],
        "repo_name": old_item["common_name"],  # Rename common_name -> repo_name
    }

    # Copy optional fields that exist in both schemas
    if "last_backup" in old_item and old_item["last_backup"] is not None:
        new_item["last_backup"] = old_item["last_backup"]

    if "os_platform" in old_item and old_item["os_platform"] is not None:
        new_item["os_platform"] = old_item["os_platform"]

    # Note: metadata field is intentionally dropped
    # New fields (last_s3_sync, passphrase, retention_*) are not set - they'll be None

    return new_item


def scan_all_items(table_name: str, dynamodb_resource: Any) -> list[dict[str, Any]]:
    """Scan all items from a DynamoDB table, handling pagination."""
    table = dynamodb_resource.Table(table_name)
    items: list[dict[str, Any]] = []

    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def batch_write_items(table_name: str, items: list[dict[str, Any]], dynamodb_resource: Any) -> int:
    """Write items to a DynamoDB table using batch_writer."""
    table = dynamodb_resource.Table(table_name)
    written_count = 0

    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            written_count += 1

    return written_count


def main() -> None:
    print(f"Starting migration from '{OLD_TABLE_NAME}' to '{NEW_TABLE_NAME}'")
    print(f"AWS Region: {AWS_REGION}")

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION, config=boto_config)

    # Read all items from old table
    print(f"\nScanning items from '{OLD_TABLE_NAME}'...")
    old_items = scan_all_items(OLD_TABLE_NAME, dynamodb)
    print(f"Found {len(old_items)} items in '{OLD_TABLE_NAME}'")

    if not old_items:
        print("No items to migrate. Exiting.")
        return

    # Transform items to new schema
    print("\nTransforming items to new schema...")
    new_items = [transform_item(item) for item in old_items]

    # Display sample transformation
    if old_items:
        print("\nSample transformation:")
        print(f"  Old item keys: {list(old_items[0].keys())}")
        print(f"  New item keys: {list(new_items[0].keys())}")

    # Write items to new table
    print(f"\nWriting {len(new_items)} items to '{NEW_TABLE_NAME}'...")
    written = batch_write_items(NEW_TABLE_NAME, new_items, dynamodb)
    print(f"Successfully wrote {written} items to '{NEW_TABLE_NAME}'")

    print("\nMigration complete!")


if __name__ == "__main__":
    main()
