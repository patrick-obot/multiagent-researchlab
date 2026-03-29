"""Tests for pilab.shared.queue — job queue convenience wrappers."""

from __future__ import annotations

import pytest

from pilab.db import store
from pilab.shared import queue
from pilab.shared.ulid import new_ulid


pytestmark = pytest.mark.asyncio


async def _seed_finding(db) -> str:
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    return fid


async def test_push_and_claim(db):
    fid = await _seed_finding(db)
    job_id = await queue.push(db, fid)
    assert job_id  # non-empty ULID string
    job = await queue.claim(db, "evaluator")
    assert job is not None
    assert job["finding_id"] == fid


async def test_claim_empty(db):
    assert await queue.claim(db, "evaluator") is None


async def test_done(db):
    fid = await _seed_finding(db)
    job_id = await queue.push(db, fid)
    await queue.claim(db, "evaluator")
    await queue.done(db, job_id)
    assert await queue.claim(db, "evaluator") is None


async def test_fail(db):
    fid = await _seed_finding(db)
    job_id = await queue.push(db, fid)
    await queue.claim(db, "evaluator")
    await queue.fail(db, job_id, "oops")
    assert await queue.claim(db, "evaluator") is None


async def test_reap_stale(db):
    fid = await _seed_finding(db)
    job_id = await queue.push(db, fid)
    await queue.claim(db, "evaluator")
    # Backdate claimed_at so the reaper sees it as stale
    await db.execute(
        "UPDATE job_queue SET claimed_at = '2020-01-01T00:00:00Z' WHERE id = ?",
        (job_id,),
    )
    await db.commit()
    reaped = await queue.reap_stale(db, 60)
    assert reaped == 1
    job = await queue.claim(db, "evaluator")
    assert job is not None
