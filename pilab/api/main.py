"""PiLab central data API.

Runs on Mac Mini M4 and owns the SQLite database.  All agents and the
dashboard communicate through this API instead of accessing the DB file
directly.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pilab import config
from pilab.db import store
from pilab.shared.ulid import new_ulid

log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# App lifecycle
# -------------------------------------------------------------------

db: aiosqlite.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
    log.info("Opening database at %s", config.DB_PATH)
    db = await store.open_db()
    yield
    if db:
        await db.close()


app = FastAPI(title="PiLab API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db() -> aiosqlite.Connection:
    assert db is not None, "Database not initialised"
    return db


# -------------------------------------------------------------------
# Request / response models
# -------------------------------------------------------------------

class FindingIn(BaseModel):
    id: str | None = None
    title: str
    summary: str | None = None
    source_type: str
    source_url: str | None = None
    topic_tags: str | None = None
    raw_content: str | None = None
    scout_pi: str | None = None
    status: str = "scouted"


class EvaluationIn(BaseModel):
    id: str | None = None
    finding_id: str
    novelty_score: int | None = None
    pi_feasibility_score: int | None = None
    feasibility_notes: str | None = None
    ram_estimate_gb: float | None = None
    requires_gpu: bool = False
    verdict: str | None = None
    verdict_reason: str | None = None
    evaluated_by: str | None = None


class ProjectIn(BaseModel):
    id: str | None = None
    finding_id: str
    evaluation_id: str | None = None
    title: str
    status: str = "awaiting_approval"
    topic_tags: str | None = None


class MilestoneIn(BaseModel):
    id: str | None = None
    project_id: str
    sequence: int
    title: str
    description: str | None = None
    done_condition: str | None = None
    category: str | None = None
    estimated_days: int | None = None
    status: str = "pending"


class MilestoneStatusIn(BaseModel):
    status: str


class LearningIn(BaseModel):
    id: str | None = None
    project_id: str
    milestone_id: str | None = None
    category: str | None = None
    note: str
    agent: str | None = None


class RejectionIn(BaseModel):
    id: str | None = None
    finding_id: str
    evaluation_id: str | None = None
    reason_code: str | None = None
    reason_detail: str | None = None


class EventIn(BaseModel):
    id: str | None = None
    agent_name: str
    event_type: str
    entity_id: str | None = None
    message: str | None = None


class JobIn(BaseModel):
    finding_id: str


class SeenUrlIn(BaseModel):
    hash: str


class FindingStatusIn(BaseModel):
    status: str


# -------------------------------------------------------------------
# Findings
# -------------------------------------------------------------------

@app.get("/findings")
async def list_findings(
    status: str | None = None,
    topic: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    return await store.list_findings(
        _db(), status=status, topic=topic, limit=limit, offset=offset
    )


@app.get("/findings/{finding_id}")
async def get_finding(finding_id: str) -> dict[str, Any]:
    row = await store.get_finding(_db(), finding_id)
    if not row:
        raise HTTPException(404, "Finding not found")
    return row


@app.post("/findings", status_code=201)
async def create_finding(body: FindingIn) -> dict[str, Any]:
    fid = body.id or new_ulid()
    await store.insert_finding(
        _db(),
        id=fid,
        title=body.title,
        summary=body.summary,
        source_type=body.source_type,
        source_url=body.source_url,
        topic_tags=body.topic_tags,
        raw_content=body.raw_content,
        scout_pi=body.scout_pi,
        status=body.status,
    )
    return {"id": fid}


@app.patch("/findings/{finding_id}/status")
async def update_finding_status(finding_id: str, body: FindingStatusIn) -> dict[str, str]:
    await store.update_finding_status(_db(), finding_id, body.status)
    return {"status": "ok"}


# -------------------------------------------------------------------
# Evaluations
# -------------------------------------------------------------------

@app.get("/evaluations/{finding_id}")
async def get_evaluation(finding_id: str) -> dict[str, Any]:
    row = await store.get_evaluation_by_finding(_db(), finding_id)
    if not row:
        raise HTTPException(404, "Evaluation not found")
    return row


@app.post("/evaluations", status_code=201)
async def create_evaluation(body: EvaluationIn) -> dict[str, Any]:
    eid = body.id or new_ulid()
    await store.insert_evaluation(
        _db(),
        id=eid,
        finding_id=body.finding_id,
        novelty_score=body.novelty_score,
        pi_feasibility_score=body.pi_feasibility_score,
        feasibility_notes=body.feasibility_notes,
        ram_estimate_gb=body.ram_estimate_gb,
        requires_gpu=body.requires_gpu,
        verdict=body.verdict,
        verdict_reason=body.verdict_reason,
        evaluated_by=body.evaluated_by,
    )
    return {"id": eid}


# -------------------------------------------------------------------
# Projects
# -------------------------------------------------------------------

@app.get("/projects")
async def list_projects(
    status: str | None = None, topic: str | None = None
) -> list[dict[str, Any]]:
    return await store.list_projects(_db(), status=status, topic=topic)


@app.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    row = await store.get_project(_db(), project_id)
    if not row:
        raise HTTPException(404, "Project not found")
    return row


@app.post("/projects", status_code=201)
async def create_project(body: ProjectIn) -> dict[str, Any]:
    pid = body.id or new_ulid()
    await store.insert_project(
        _db(),
        id=pid,
        finding_id=body.finding_id,
        evaluation_id=body.evaluation_id,
        title=body.title,
        status=body.status,
        topic_tags=body.topic_tags,
    )
    return {"id": pid}


@app.post("/projects/{project_id}/approve")
async def approve_project(project_id: str) -> dict[str, str]:
    proj = await store.get_project(_db(), project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    await store.approve_project(_db(), project_id)
    return {"status": "approved"}


@app.patch("/projects/{project_id}/status")
async def update_project_status(
    project_id: str, body: MilestoneStatusIn
) -> dict[str, str]:
    await store.update_project_status(_db(), project_id, body.status)
    return {"status": "ok"}


# -------------------------------------------------------------------
# Milestones
# -------------------------------------------------------------------

@app.get("/projects/{project_id}/milestones")
async def list_milestones(project_id: str) -> list[dict[str, Any]]:
    return await store.list_milestones(_db(), project_id)


@app.post("/milestones", status_code=201)
async def create_milestone(body: MilestoneIn) -> dict[str, Any]:
    mid = body.id or new_ulid()
    await store.insert_milestone(
        _db(),
        id=mid,
        project_id=body.project_id,
        sequence=body.sequence,
        title=body.title,
        description=body.description,
        done_condition=body.done_condition,
        category=body.category,
        estimated_days=body.estimated_days,
        status=body.status,
    )
    return {"id": mid}


@app.patch("/milestones/{milestone_id}/status")
async def update_milestone_status(
    milestone_id: str, body: MilestoneStatusIn
) -> dict[str, str]:
    await store.update_milestone_status(_db(), milestone_id, body.status)
    return {"status": "ok"}


# -------------------------------------------------------------------
# Learnings
# -------------------------------------------------------------------

@app.get("/projects/{project_id}/learnings")
async def list_learnings(project_id: str) -> list[dict[str, Any]]:
    return await store.list_learnings(_db(), project_id)


@app.post("/learnings", status_code=201)
async def create_learning(body: LearningIn) -> dict[str, Any]:
    lid = body.id or new_ulid()
    await store.insert_learning(
        _db(),
        id=lid,
        project_id=body.project_id,
        milestone_id=body.milestone_id,
        category=body.category,
        note=body.note,
        agent=body.agent,
    )
    return {"id": lid}


@app.get("/milestones/{milestone_id}/has-learning")
async def has_learning(milestone_id: str) -> dict[str, bool]:
    result = await store.has_learning_for_milestone(_db(), milestone_id)
    return {"has_learning": result}


# -------------------------------------------------------------------
# Rejections
# -------------------------------------------------------------------

@app.get("/rejections")
async def list_rejections(
    reason_code: str | None = None, limit: int = Query(50, le=500)
) -> list[dict[str, Any]]:
    return await store.list_rejections(
        _db(), reason_code=reason_code, limit=limit
    )


@app.post("/rejections", status_code=201)
async def create_rejection(body: RejectionIn) -> dict[str, Any]:
    rid = body.id or new_ulid()
    await store.insert_rejection(
        _db(),
        id=rid,
        finding_id=body.finding_id,
        evaluation_id=body.evaluation_id,
        reason_code=body.reason_code,
        reason_detail=body.reason_detail,
    )
    return {"id": rid}


# -------------------------------------------------------------------
# Events
# -------------------------------------------------------------------

@app.get("/events")
async def list_events(limit: int = Query(50, le=500)) -> list[dict[str, Any]]:
    return await store.list_events(_db(), limit=limit)


@app.post("/events", status_code=201)
async def create_event(body: EventIn) -> dict[str, Any]:
    eid = body.id or new_ulid()
    await store.insert_event(
        _db(),
        id=eid,
        agent_name=body.agent_name,
        event_type=body.event_type,
        entity_id=body.entity_id,
        message=body.message,
    )
    return {"id": eid}


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------

@app.get("/stats")
async def get_stats() -> dict[str, Any]:
    return await store.get_stats(_db())


# -------------------------------------------------------------------
# Job queue
# -------------------------------------------------------------------

@app.post("/jobs", status_code=201)
async def enqueue_job(body: JobIn) -> dict[str, Any]:
    job_id = new_ulid()
    await store.enqueue_job(_db(), id=job_id, finding_id=body.finding_id)
    return {"id": job_id}


@app.post("/jobs/claim")
async def claim_job(claimed_by: str = Query(...)) -> dict[str, Any]:
    job = await store.claim_job(_db(), claimed_by)
    if not job:
        raise HTTPException(404, "No pending jobs")
    return job


@app.patch("/jobs/{job_id}/done")
async def complete_job(job_id: str) -> dict[str, str]:
    await store.complete_job(_db(), job_id)
    return {"status": "done"}


@app.patch("/jobs/{job_id}/fail")
async def fail_job(job_id: str, error_message: str = Query("")) -> dict[str, str]:
    await store.fail_job(_db(), job_id, error_message)
    return {"status": "error"}


@app.post("/jobs/reap")
async def reap_stale_jobs() -> dict[str, int]:
    count = await store.reap_stale_jobs(_db(), config.EVALUATOR_JOB_CLAIM_TIMEOUT)
    return {"reaped": count}


# -------------------------------------------------------------------
# Seen URLs
# -------------------------------------------------------------------

@app.get("/seen-urls/{url_hash}")
async def check_seen_url(url_hash: str) -> dict[str, bool]:
    seen = await store.is_url_seen(_db(), url_hash)
    return {"seen": seen}


@app.post("/seen-urls", status_code=201)
async def mark_seen_url(body: SeenUrlIn) -> dict[str, str]:
    await store.mark_url_seen(_db(), body.hash)
    return {"status": "ok"}


# -------------------------------------------------------------------
# Recent titles (evaluator context)
# -------------------------------------------------------------------

@app.get("/recent-titles")
async def recent_titles(limit: int = Query(20, le=100)) -> list[str]:
    return await store.recent_titles(_db(), limit=limit)


# -------------------------------------------------------------------
# Static dashboard (served from /dashboard/ or root fallback)
# -------------------------------------------------------------------

_dashboard_dir = Path(__file__).parent.parent / "dashboard"
if _dashboard_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_dashboard_dir), html=True))
