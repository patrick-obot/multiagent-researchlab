"""Tests for pilab.db.migrate — schema migration runner."""

from __future__ import annotations

import pytest
import aiosqlite
from pathlib import Path
from unittest.mock import patch

from pilab.db.migrate import current_version, apply_migrations, MIGRATIONS_DIR


pytestmark = pytest.mark.asyncio


async def _fresh_db() -> aiosqlite.Connection:
    """Create an in-memory DB with schema applied (no row_factory, since
    migrate.py uses tuple indexing like row[0])."""
    conn = await aiosqlite.connect(":memory:")
    schema = Path(__file__).parent.parent / "pilab" / "db" / "schema.sql"
    await conn.executescript(schema.read_text())
    await conn.commit()
    return conn


async def test_current_version_after_init():
    db = await _fresh_db()
    ver = await current_version(db)
    assert ver == 1
    await db.close()


async def test_current_version_no_table():
    db = await aiosqlite.connect(":memory:")
    ver = await current_version(db)
    assert ver == 0
    await db.close()


async def test_apply_migrations_no_pending():
    db = await _fresh_db()
    ver = await apply_migrations(db)
    assert ver == 1
    await db.close()


async def test_apply_migrations_with_file(tmp_path):
    db = await _fresh_db()
    # Create a fake migration file
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "0002.sql").write_text(
        "CREATE TABLE IF NOT EXISTS test_mig (x TEXT);\n"
    )
    with patch("pilab.db.migrate.MIGRATIONS_DIR", mig_dir):
        ver = await apply_migrations(db)
    assert ver == 2
    # Verify table was created
    async with db.execute("SELECT 1 FROM test_mig LIMIT 1") as cur:
        pass  # no error means table exists
    await db.close()
