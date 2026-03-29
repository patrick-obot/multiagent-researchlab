"""Convenience wrappers around the job-queue store functions.

These are thin helpers that combine ULID generation with store calls
so agents don't have to import both modules.
"""

from __future__ import annotations

import aiosqlite

from pilab.db import store
from pilab.shared.ulid import new_ulid


async def push(db: aiosqlite.Connection, finding_id: str) -> str:
    """Create a new pending job for *finding_id*.  Returns the job ID."""
    job_id = new_ulid()
    await store.enqueue_job(db, id=job_id, finding_id=finding_id)
    return job_id


async def claim(db: aiosqlite.Connection, claimed_by: str) -> store.Row | None:
    """Claim the next pending job.  Returns the job row or ``None``."""
    return await store.claim_job(db, claimed_by)


async def done(db: aiosqlite.Connection, job_id: str) -> None:
    """Mark a job as successfully completed."""
    await store.complete_job(db, job_id)


async def fail(db: aiosqlite.Connection, job_id: str, error: str) -> None:
    """Mark a job as failed with an error message."""
    await store.fail_job(db, job_id, error)


async def reap_stale(db: aiosqlite.Connection, timeout_seconds: int) -> int:
    """Reset jobs that have been claimed too long back to pending."""
    return await store.reap_stale_jobs(db, timeout_seconds)
