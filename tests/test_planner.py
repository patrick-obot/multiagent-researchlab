"""Tests for pilab.planner — milestone generation and monitoring."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pilab.planner.planning import generate_milestones
from pilab.planner.monitor import check_milestones


pytestmark = pytest.mark.asyncio


def _make_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


# -------------------------------------------------------------------
# Planning
# -------------------------------------------------------------------

def _planning_client():
    """Mock client for generate_milestones tests."""
    post_calls = []

    async def mock_get(url, **kwargs):
        if "/findings/" in url:
            return _make_response({
                "id": "f1", "title": "Finding", "summary": "A summary",
                "topic_tags": "ai,edge",
            })
        elif "/evaluations/" in url:
            return _make_response({
                "feasibility_notes": "Looks good", "ram_estimate_gb": 4.0,
            })
        return _make_response({})

    async def mock_post(url, **kwargs):
        post_calls.append((url, kwargs.get("json", {})))
        return _make_response({"id": "new_id"}, 201)

    async def mock_patch(url, **kwargs):
        return _make_response({"status": "ok"})

    client = MagicMock()
    client.get = mock_get
    client.post = mock_post
    client.patch = mock_patch
    client._post_calls = post_calls
    return client


async def test_generate_milestones():
    client = _planning_client()
    project = {"id": "p1", "finding_id": "f1", "title": "Test Project"}
    milestones_data = [
        {"sequence": 1, "title": "Setup env", "description": "Install deps",
         "done_condition": "venv works", "category": "setup", "estimated_days": 1},
        {"sequence": 2, "title": "Implement", "description": "Code it",
         "done_condition": "tests pass", "category": "implementation", "estimated_days": 2},
        {"sequence": 3, "title": "Document", "description": "Write docs",
         "done_condition": "README updated", "category": "documentation", "estimated_days": 1},
    ]

    with patch("pilab.planner.planning.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = milestones_data
        await generate_milestones(client, project)

    post_urls = [url for url, _ in client._post_calls]
    # 3 milestones + 1 event = 4 posts
    milestone_posts = [u for u in post_urls if "/milestones" in u]
    event_posts = [u for u in post_urls if "/events" in u]
    assert len(milestone_posts) == 3
    assert len(event_posts) == 1


async def test_generate_milestones_non_list():
    """If LLM returns non-list, should log error and return early."""
    client = _planning_client()
    project = {"id": "p1", "finding_id": "f1", "title": "Test"}

    with patch("pilab.planner.planning.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"error": "bad output"}
        await generate_milestones(client, project)

    milestone_posts = [u for u, _ in client._post_calls if "/milestones" in u]
    assert len(milestone_posts) == 0


# -------------------------------------------------------------------
# Monitor
# -------------------------------------------------------------------

def _monitor_client(has_learning=False, all_completed=True):
    """Mock client for check_milestones tests."""
    post_calls = []

    async def mock_get(url, **kwargs):
        params = kwargs.get("params", {})
        if "/projects" in url and params.get("status") == "in_progress":
            return _make_response([{"id": "p1", "title": "Project 1"}])
        elif "/has-learning" in url:
            return _make_response({"has_learning": has_learning})
        elif "/milestones" in url:
            status = "completed" if all_completed else "in_progress"
            return _make_response([
                {"id": "ms1", "title": "Setup", "status": status,
                 "description": "Desc", "done_condition": "Done"},
            ])
        return _make_response({})

    async def mock_post(url, **kwargs):
        post_calls.append((url, kwargs.get("json", {})))
        return _make_response({"id": "new"}, 201)

    async def mock_patch(url, **kwargs):
        return _make_response({"status": "ok"})

    client = MagicMock()
    client.get = mock_get
    client.post = mock_post
    client.patch = mock_patch
    client._post_calls = post_calls
    return client


async def test_check_milestones_generates_learning():
    client = _monitor_client(has_learning=False, all_completed=True)

    with patch("pilab.planner.monitor.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"category": "hardware", "note": "Pi handles 7B at 15 tok/s"}
        await check_milestones(client)

    post_urls = [url for url, _ in client._post_calls]
    assert any("/learnings" in u for u in post_urls)
    assert any("/events" in u for u in post_urls)


async def test_check_milestones_skips_existing_learning():
    client = _monitor_client(has_learning=True, all_completed=True)

    with patch("pilab.planner.monitor.call_json", new_callable=AsyncMock) as mock_llm:
        await check_milestones(client)
        mock_llm.assert_not_called()


async def test_check_milestones_marks_project_completed():
    client = _monitor_client(has_learning=False, all_completed=True)

    with patch("pilab.planner.monitor.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"category": "process", "note": "Learned stuff"}
        await check_milestones(client)

    # Should have an event for project_completed
    event_posts = [(u, d) for u, d in client._post_calls if "/events" in u]
    completed_events = [d for _, d in event_posts if d.get("event_type") == "project_completed"]
    assert len(completed_events) == 1
