"""Tests for pilab.api.main — FastAPI endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from pilab.api.main import app, lifespan
from pilab.shared.ulid import new_ulid

import pilab.api.main as api_module


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(tmp_path):
    """Async test client with a temp database."""
    import os
    db_path = str(tmp_path / "test.db")
    os.environ["PILAB_DB_PATH"] = db_path
    # Reload config
    import pilab.config
    pilab.config.DB_PATH = db_path

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    # Cleanup
    if "PILAB_DB_PATH" in os.environ:
        del os.environ["PILAB_DB_PATH"]


# -------------------------------------------------------------------
# Findings
# -------------------------------------------------------------------

async def test_create_and_get_finding(client):
    resp = await client.post("/findings", json={
        "title": "Test Finding",
        "source_type": "hackernews",
        "source_url": "https://example.com",
        "topic_tags": "ai",
    })
    assert resp.status_code == 201
    fid = resp.json()["id"]

    resp = await client.get(f"/findings/{fid}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test Finding"


async def test_list_findings(client):
    await client.post("/findings", json={"title": "F1", "source_type": "rss"})
    await client.post("/findings", json={"title": "F2", "source_type": "rss"})
    resp = await client.get("/findings")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_findings_filter_status(client):
    await client.post("/findings", json={"title": "F1", "source_type": "rss", "status": "scouted"})
    await client.post("/findings", json={"title": "F2", "source_type": "rss", "status": "approved"})
    resp = await client.get("/findings", params={"status": "approved"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "F2"


async def test_get_finding_404(client):
    resp = await client.get("/findings/nonexistent")
    assert resp.status_code == 404


async def test_update_finding_status(client):
    resp = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = resp.json()["id"]
    resp = await client.patch(f"/findings/{fid}/status", json={"status": "approved"})
    assert resp.status_code == 200


# -------------------------------------------------------------------
# Evaluations
# -------------------------------------------------------------------

async def test_create_and_get_evaluation(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    resp = await client.post("/evaluations", json={
        "finding_id": fid, "novelty_score": 7,
        "pi_feasibility_score": 8, "verdict": "approved",
    })
    assert resp.status_code == 201

    resp = await client.get(f"/evaluations/{fid}")
    assert resp.status_code == 200
    assert resp.json()["novelty_score"] == 7


async def test_get_evaluation_404(client):
    resp = await client.get("/evaluations/missing")
    assert resp.status_code == 404


# -------------------------------------------------------------------
# Projects
# -------------------------------------------------------------------

async def test_create_and_list_projects(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    resp = await client.post("/projects", json={
        "finding_id": fid, "title": "Project 1", "topic_tags": "ai",
    })
    assert resp.status_code == 201

    resp = await client.get("/projects")
    assert len(resp.json()) == 1


async def test_approve_project(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    pr = await client.post("/projects", json={"finding_id": fid, "title": "P"})
    pid = pr.json()["id"]

    resp = await client.post(f"/projects/{pid}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_approve_project_404(client):
    resp = await client.post("/projects/nonexistent/approve")
    assert resp.status_code == 404


async def test_update_project_status(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    pr = await client.post("/projects", json={"finding_id": fid, "title": "P"})
    pid = pr.json()["id"]
    resp = await client.patch(f"/projects/{pid}/status", json={"status": "in_progress"})
    assert resp.status_code == 200


# -------------------------------------------------------------------
# Milestones
# -------------------------------------------------------------------

async def test_create_and_list_milestones(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    pr = await client.post("/projects", json={"finding_id": fid, "title": "P"})
    pid = pr.json()["id"]

    await client.post("/milestones", json={
        "project_id": pid, "sequence": 1, "title": "Setup", "category": "setup",
    })
    await client.post("/milestones", json={
        "project_id": pid, "sequence": 2, "title": "Build", "category": "implementation",
    })

    resp = await client.get(f"/projects/{pid}/milestones")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_update_milestone_status(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    pr = await client.post("/projects", json={"finding_id": fid, "title": "P"})
    pid = pr.json()["id"]
    mr = await client.post("/milestones", json={
        "project_id": pid, "sequence": 1, "title": "MS",
    })
    mid = mr.json()["id"]
    resp = await client.patch(f"/milestones/{mid}/status", json={"status": "completed"})
    assert resp.status_code == 200


# -------------------------------------------------------------------
# Learnings
# -------------------------------------------------------------------

async def test_create_and_list_learnings(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    pr = await client.post("/projects", json={"finding_id": fid, "title": "P"})
    pid = pr.json()["id"]

    resp = await client.post("/learnings", json={
        "project_id": pid, "note": "Learned something", "agent": "planner",
    })
    assert resp.status_code == 201

    resp = await client.get(f"/projects/{pid}/learnings")
    assert len(resp.json()) == 1


async def test_has_learning(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    pr = await client.post("/projects", json={"finding_id": fid, "title": "P"})
    pid = pr.json()["id"]
    mr = await client.post("/milestones", json={
        "project_id": pid, "sequence": 1, "title": "MS",
    })
    mid = mr.json()["id"]

    resp = await client.get(f"/milestones/{mid}/has-learning")
    assert resp.json()["has_learning"] is False

    await client.post("/learnings", json={
        "project_id": pid, "milestone_id": mid, "note": "Note", "agent": "planner",
    })
    resp = await client.get(f"/milestones/{mid}/has-learning")
    assert resp.json()["has_learning"] is True


# -------------------------------------------------------------------
# Rejections
# -------------------------------------------------------------------

async def test_create_and_list_rejections(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]
    resp = await client.post("/rejections", json={
        "finding_id": fid, "reason_code": "requires_gpu",
    })
    assert resp.status_code == 201

    resp = await client.get("/rejections")
    assert len(resp.json()) == 1


# -------------------------------------------------------------------
# Events
# -------------------------------------------------------------------

async def test_create_and_list_events(client):
    resp = await client.post("/events", json={
        "agent_name": "scout", "event_type": "new_finding", "message": "Found",
    })
    assert resp.status_code == 201

    resp = await client.get("/events")
    assert len(resp.json()) == 1


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------

async def test_stats_empty(client):
    resp = await client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rejections_total"] == 0


# -------------------------------------------------------------------
# Job queue
# -------------------------------------------------------------------

async def test_job_queue_workflow(client):
    fr = await client.post("/findings", json={"title": "F", "source_type": "rss"})
    fid = fr.json()["id"]

    # Enqueue
    resp = await client.post("/jobs", json={"finding_id": fid})
    assert resp.status_code == 201

    # Claim
    resp = await client.post("/jobs/claim", params={"claimed_by": "evaluator"})
    assert resp.status_code == 200
    jid = resp.json()["id"]

    # Complete
    resp = await client.patch(f"/jobs/{jid}/done")
    assert resp.status_code == 200

    # No more jobs
    resp = await client.post("/jobs/claim", params={"claimed_by": "evaluator"})
    assert resp.status_code == 404


async def test_job_claim_empty(client):
    resp = await client.post("/jobs/claim", params={"claimed_by": "evaluator"})
    assert resp.status_code == 404


async def test_job_reap(client):
    resp = await client.post("/jobs/reap")
    assert resp.status_code == 200
    assert resp.json()["reaped"] == 0


# -------------------------------------------------------------------
# Seen URLs
# -------------------------------------------------------------------

async def test_seen_urls(client):
    resp = await client.get("/seen-urls/abc123")
    assert resp.json()["seen"] is False

    resp = await client.post("/seen-urls", json={"hash": "abc123"})
    assert resp.status_code == 201

    resp = await client.get("/seen-urls/abc123")
    assert resp.json()["seen"] is True


# -------------------------------------------------------------------
# Recent titles
# -------------------------------------------------------------------

async def test_recent_titles_empty(client):
    resp = await client.get("/recent-titles")
    assert resp.status_code == 200
    assert resp.json() == []
