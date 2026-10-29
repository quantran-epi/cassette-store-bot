"""CLI script to import legacy JSON blob into SQLite database.

Usage:
    python -m scripts.import_legacy_blob --blob backup/blob --dry-run
    python -m scripts.import_legacy_blob --blob backup/blob --apply
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.db.connection import get_db_connection
from src.db.schema import init_db
from src.services.legacy_importer import LegacyBlobImporter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("import_legacy_blob")


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy backup/blob into SQLite DB")
    parser.add_argument(
        "--blob",
        type=str,
        default="backup/blob",
        help="Path to legacy backup/blob JSON file (default: backup/blob)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate import without modifying database (default: True)",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Execute real import with transaction commit",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite database file (default from settings)",
    )
    return parser.parse_args(args)


async def run_import(blob_path: str, dry_run: bool, db_path: str | None = None) -> int:
    path = Path(blob_path)
    if not path.is_file():
        logger.error("Blob file not found: %s", blob_path)
        return 1

    mode_str = "DRY-RUN (Simulated)" if dry_run else "APPLY (Real DB write)"
    print(f"\n{'='*50}")
    print(f"LEGACY BLOB MIGRATION: {mode_str}")
    print(f"Blob path: {blob_path}")
    print(f"{'='*50}\n")

    importer = LegacyBlobImporter(path)

    async with get_db_connection(db_path) as db:
        await init_db(db)
        summary = await importer.run(db, dry_run=dry_run)

    print("\n--- Migration Results ---")
    print(f"Customers Created: {summary.customers_created}")
    print(f"Customers Reused : {summary.customers_reused}")
    print(f"Orders Created   : {summary.orders_created}")
    print(f"Orders Skipped   : {summary.orders_skipped}")
    if summary.errors:
        print(f"Errors ({len(summary.errors)}):")
        for err in summary.errors:
            print(f"  - {err}")
        return 1

    print("\nStatus: SUCCESS\n")
    return 0


def main() -> None:
    args = parse_args()
    dry_run = not args.apply
    sys.exit(asyncio.run(run_import(args.blob, dry_run=dry_run, db_path=args.db)))


if __name__ == "__main__":
    main()
