"""Tests for pilab.db.store — typed DB helper functions."""

from __future__ import annotations

import pytest

from pilab.db import store
from pilab.shared.ulid import new_ulid


pytestmark = pytest.mark.asyncio


# -------------------------------------------------------------------
# Findings
# -------------------------------------------------------------------

async def test_insert_and_get_finding(db):
    fid = new_ulid()
    await store.insert_finding(
        db, id=fid, title="Test Finding", source_type="hackernews",
        source_url="https://example.com", topic_tags="ai,edge",
        summary="A summary", raw_content="raw", scout_pi="pi2",
    )
    row = await store.get_finding(db, fid)
    assert row is not None
    assert row["title"] == "Test Finding"
    assert row["source_type"] == "hackernews"
    assert row["topic_tags"] == "ai,edge"
    assert row["status"] == "scouted"


async def test_get_finding_not_found(db):
    assert await store.get_finding(db, "nonexistent") is None


async def test_list_findings_empty(db):
    rows = await store.list_findings(db)
    assert rows == []


async def test_list_findings_filter_by_status(db):
    fid1, fid2 = new_ulid(), new_ulid()
    await store.insert_finding(db, id=fid1, title="F1", source_type="rss", status="scouted")
    await store.insert_finding(db, id=fid2, title="F2", source_type="rss", status="approved")
    rows = await store.list_findings(db, status="scouted")
    assert len(rows) == 1
    assert rows[0]["id"] == fid1


async def test_list_findings_filter_by_topic(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="AI Thing", source_type="rss", topic_tags="ai,edge")
    rows = await store.list_findings(db, topic="ai")
    assert len(rows) == 1
    rows = await store.list_findings(db, topic="fintech")
    assert len(rows) == 0


async def test_list_findings_pagination(db):
    for i in range(5):
        await store.insert_finding(db, id=new_ulid(), title=f"F{i}", source_type="rss")
    rows = await store.list_findings(db, limit=2, offset=0)
    assert len(rows) == 2
    rows = await store.list_findings(db, limit=2, offset=4)
    assert len(rows) == 1


async def test_update_finding_status(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    await store.update_finding_status(db, fid, "approved")
    row = await store.get_finding(db, fid)
    assert row["status"] == "approved"


# -------------------------------------------------------------------
# Evaluations
# -------------------------------------------------------------------

async def test_insert_and_get_evaluation(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    eid = new_ulid()
    await store.insert_evaluation(
        db, id=eid, finding_id=fid, novelty_score=7,
        pi_feasibility_score=8, feasibility_notes="Good",
        ram_estimate_gb=4.0, requires_gpu=False,
        verdict="approved", evaluated_by="evaluator",
    )
    row = await store.get_evaluation_by_finding(db, fid)
    assert row is not None
    assert row["novelty_score"] == 7
    assert row["pi_feasibility_score"] == 8
    assert row["requires_gpu"] == 0  # stored as int
    assert row["verdict"] == "approved"


async def test_get_evaluation_not_found(db):
    assert await store.get_evaluation_by_finding(db, "missing") is None


# -------------------------------------------------------------------
# Projects
# -------------------------------------------------------------------

async def test_insert_and_get_project(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="Test Project", topic_tags="ai")
    row = await store.get_project(db, pid)
    assert row is not None
    assert row["title"] == "Test Project"
    assert row["status"] == "awaiting_approval"


async def test_list_projects_filter(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P1", status="in_progress", topic_tags="ai")
    rows = await store.list_projects(db, status="in_progress")
    assert len(rows) == 1
    rows = await store.list_projects(db, status="completed")
    assert len(rows) == 0


async def test_update_project_status_in_progress(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P")
    await store.update_project_status(db, pid, "in_progress")
    row = await store.get_project(db, pid)
    assert row["status"] == "in_progress"
    assert row["started_at"] is not None


async def test_update_project_status_completed(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P")
    await store.update_project_status(db, pid, "completed")
    row = await store.get_project(db, pid)
    assert row["status"] == "completed"
    assert row["completed_at"] is not None


async def test_approve_project(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P")
    await store.approve_project(db, pid, approved_by="tester")
    row = await store.get_project(db, pid)
    assert row["status"] == "approved"
    assert row["approved_by"] == "tester"
    assert row["approved_at"] is not None


# -------------------------------------------------------------------
# Milestones
# -------------------------------------------------------------------

async def test_insert_and_list_milestones(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P")

    for seq in range(1, 4):
        await store.insert_milestone(
            db, id=new_ulid(), project_id=pid, sequence=seq,
            title=f"MS {seq}", category="setup",
        )
    rows = await store.list_milestones(db, pid)
    assert len(rows) == 3
    assert rows[0]["sequence"] == 1
    assert rows[2]["sequence"] == 3


async def test_update_milestone_status_completed(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P")
    mid = new_ulid()
    await store.insert_milestone(db, id=mid, project_id=pid, sequence=1, title="MS")
    await store.update_milestone_status(db, mid, "completed")
    rows = await store.list_milestones(db, pid)
    assert rows[0]["status"] == "completed"
    assert rows[0]["completed_at"] is not None


# -------------------------------------------------------------------
# Learnings
# -------------------------------------------------------------------

async def test_insert_and_list_learnings(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P")
    mid = new_ulid()
    await store.insert_milestone(db, id=mid, project_id=pid, sequence=1, title="MS")
    lid = new_ulid()
    await store.insert_learning(
        db, id=lid, project_id=pid, milestone_id=mid,
        category="hardware", note="It works", agent="planner",
    )
    rows = await store.list_learnings(db, pid)
    assert len(rows) == 1
    assert rows[0]["note"] == "It works"


async def test_has_learning_for_milestone(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    pid = new_ulid()
    await store.insert_project(db, id=pid, finding_id=fid, title="P")
    mid = new_ulid()
    await store.insert_milestone(db, id=mid, project_id=pid, sequence=1, title="MS")

    assert await store.has_learning_for_milestone(db, mid) is False
    await store.insert_learning(
        db, id=new_ulid(), project_id=pid, milestone_id=mid,
        note="Learn", agent="planner",
    )
    assert await store.has_learning_for_milestone(db, mid) is True


# -------------------------------------------------------------------
# Rejections
# -------------------------------------------------------------------

async def test_insert_and_list_rejections(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    rid = new_ulid()
    await store.insert_rejection(
        db, id=rid, finding_id=fid, reason_code="requires_gpu",
        reason_detail="Needs CUDA",
    )
    rows = await store.list_rejections(db)
    assert len(rows) == 1
    assert rows[0]["reason_code"] == "requires_gpu"


async def test_list_rejections_filter(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    await store.insert_rejection(db, id=new_ulid(), finding_id=fid, reason_code="requires_gpu")
    await store.insert_rejection(db, id=new_ulid(), finding_id=fid, reason_code="not_novel")
    rows = await store.list_rejections(db, reason_code="not_novel")
    assert len(rows) == 1


# -------------------------------------------------------------------
# Agent events
# -------------------------------------------------------------------

async def test_insert_and_list_events(db):
    eid = new_ulid()
    await store.insert_event(
        db, id=eid, agent_name="scout", event_type="new_finding",
        entity_id="abc", message="Found something",
    )
    rows = await store.list_events(db)
    assert len(rows) == 1
    assert rows[0]["agent_name"] == "scout"


async def test_last_heartbeat(db):
    assert await store.last_heartbeat(db, "scout") is None
    await store.insert_event(
        db, id=new_ulid(), agent_name="scout", event_type="heartbeat",
        message="alive",
    )
    hb = await store.last_heartbeat(db, "scout")
    assert hb is not None


# -------------------------------------------------------------------
# Seen URLs
# -------------------------------------------------------------------

async def test_seen_urls(db):
    h = "abc123hash"
    assert await store.is_url_seen(db, h) is False
    await store.mark_url_seen(db, h)
    assert await store.is_url_seen(db, h) is True


async def test_mark_url_seen_idempotent(db):
    h = "dup_hash"
    await store.mark_url_seen(db, h)
    await store.mark_url_seen(db, h)  # should not raise
    assert await store.is_url_seen(db, h) is True


# -------------------------------------------------------------------
# Job queue
# -------------------------------------------------------------------

async def test_enqueue_and_claim_job(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    jid = new_ulid()
    await store.enqueue_job(db, id=jid, finding_id=fid)
    job = await store.claim_job(db, "evaluator")
    assert job is not None
    assert job["id"] == jid
    assert job["status"] == "claimed"
    assert job["claimed_by"] == "evaluator"


async def test_claim_job_empty_queue(db):
    assert await store.claim_job(db, "evaluator") is None


async def test_complete_job(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    jid = new_ulid()
    await store.enqueue_job(db, id=jid, finding_id=fid)
    await store.claim_job(db, "evaluator")
    await store.complete_job(db, jid)
    # Should not be claimable again
    assert await store.claim_job(db, "evaluator") is None


async def test_fail_job(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    jid = new_ulid()
    await store.enqueue_job(db, id=jid, finding_id=fid)
    await store.claim_job(db, "evaluator")
    await store.fail_job(db, jid, "boom")
    # Failed job should not be claimable
    assert await store.claim_job(db, "evaluator") is None


async def test_reap_stale_jobs(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss")
    jid = new_ulid()
    await store.enqueue_job(db, id=jid, finding_id=fid)
    await store.claim_job(db, "evaluator")
    # Backdate claimed_at so the reaper sees it as stale
    await db.execute(
        "UPDATE job_queue SET claimed_at = '2020-01-01T00:00:00Z' WHERE id = ?",
        (jid,),
    )
    await db.commit()
    reaped = await store.reap_stale_jobs(db, 60)
    assert reaped == 1
    # Should be claimable again
    job = await store.claim_job(db, "evaluator")
    assert job is not None


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------

async def test_get_stats_empty(db):
    stats = await store.get_stats(db)
    assert stats["rejections_total"] == 0
    assert stats["scouted_this_week"] == 0


async def test_get_stats_with_data(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="F", source_type="rss", status="scouted")
    stats = await store.get_stats(db)
    assert stats.get("findings_scouted", 0) >= 1
    assert stats["scouted_this_week"] >= 1


# -------------------------------------------------------------------
# Recent titles
# -------------------------------------------------------------------

async def test_recent_titles(db):
    fid = new_ulid()
    await store.insert_finding(db, id=fid, title="Cool Paper", source_type="arxiv")
    eid = new_ulid()
    await store.insert_evaluation(db, id=eid, finding_id=fid, verdict="approved")
    titles = await store.recent_titles(db)
    assert "Cool Paper" in titles


async def test_recent_titles_empty(db):
    assert await store.recent_titles(db) == []
