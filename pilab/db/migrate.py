"""Simple forward-only schema migration runner.

Migration files live in ``pilab/db/migrations/`` named ``NNNN.sql`` where
NNNN is the version number (zero-padded to 4 digits).  The initial schema
(schema.sql) is version 1 and is applied by ``init_db``, not by this runner.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def current_version(db: aiosqlite.Connection) -> int:
    """Return the highest applied schema version, or 0 if uninitialised."""
    try:
        async with db.execute(
            "SELECT MAX(version) FROM schema_version"
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return 0
            # Handle both dict rows (_row_factory) and tuple rows
            val = row["MAX(version)"] if isinstance(row, dict) else row[0]
            return val if val is not None else 0
    except aiosqlite.OperationalError:
        return 0


async def apply_migrations(db: aiosqlite.Connection) -> int:
    """Apply all pending migration files and return the new version."""
    if not MIGRATIONS_DIR.exists():
        MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
        return await current_version(db)

    cur_ver = await current_version(db)
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    applied = 0

    for path in sql_files:
        try:
            file_ver = int(path.stem)
        except ValueError:
            log.warning("Skipping non-numeric migration file: %s", path.name)
            continue

        if file_ver <= cur_ver:
            continue

        log.info("Applying migration %04d from %s", file_ver, path.name)
        sql = path.read_text()
        await db.executescript(sql)
        await db.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (file_ver,)
        )
        await db.commit()
        applied += 1

    if applied:
        new_ver = await current_version(db)
        log.info("Migrations complete — now at version %d", new_ver)
        return new_ver

    log.info("No pending migrations (at version %d)", cur_ver)
    return cur_ver
