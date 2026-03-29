"""Shared test fixtures."""

from __future__ import annotations

import pytest_asyncio
import aiosqlite

from pilab.db.store import _row_factory


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database with schema applied."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = _row_factory
    await conn.execute("PRAGMA foreign_keys = ON")

    from pathlib import Path
    schema = Path(__file__).parent.parent / "pilab" / "db" / "schema.sql"
    await conn.executescript(schema.read_text())
    await conn.commit()
    yield conn
    await conn.close()
