#!/usr/bin/env python3
"""Create a PostgreSQL database for tests.

Usage:
  python scripts/create_test_db.py
  python scripts/create_test_db.py --database infosentry_test
  python scripts/create_test_db.py --database infosentry_test --extensions vector
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
import structlog
from psycopg import errors, sql

from src.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


logger = structlog.get_logger(__name__)


def _connect(settings: Settings, database: str) -> psycopg.Connection[Any]:
    return psycopg.connect(
        dbname=database,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        autocommit=True,
    )


def create_database(settings: Settings, target_db: str, maintenance_db: str) -> None:
    if not target_db:
        raise ValueError("Target database name is empty.")
    if not maintenance_db:
        raise ValueError("Maintenance database name is empty.")

    logger.info(
        "create_test_db.start",
        target_db=target_db,
        maintenance_db=maintenance_db,
    )

    try:
        with _connect(settings, maintenance_db) as conn:
            conn.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db))
            )
        logger.info("create_test_db.created", target_db=target_db)
    except errors.DuplicateDatabase:
        logger.info("create_test_db.exists", target_db=target_db)
    except Exception:
        logger.exception("create_test_db.failed", target_db=target_db)
        raise


def create_extensions(settings: Settings, target_db: str, extensions: list[str]) -> None:
    if not extensions:
        return
    logger.info("create_test_db.extensions.start", target_db=target_db, extensions=extensions)
    try:
        with _connect(settings, target_db) as conn:
            for extension in extensions:
                conn.execute(
                    sql.SQL("CREATE EXTENSION IF NOT EXISTS {}").format(
                        sql.Identifier(extension)
                    )
                )
        logger.info(
            "create_test_db.extensions.done",
            target_db=target_db,
            extensions=extensions,
        )
    except Exception:
        logger.exception(
            "create_test_db.extensions.failed",
            target_db=target_db,
            extensions=extensions,
        )
        raise


def _parse_args(settings: Settings) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a PostgreSQL database")
    parser.add_argument(
        "--database",
        default=settings.POSTGRES_DB,
        help="Target database name (defaults to POSTGRES_DB).",
    )
    parser.add_argument(
        "--maintenance-db",
        default=os.getenv("POSTGRES_MAINTENANCE_DB", "postgres"),
        help="Maintenance database used to run CREATE DATABASE.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=[],
        help="Extensions to create in the target database.",
    )
    return parser.parse_args()


def main() -> None:
    settings = Settings()
    args = _parse_args(settings)
    create_database(settings, args.database, args.maintenance_db)
    create_extensions(settings, args.database, args.extensions)


if __name__ == "__main__":
    main()
