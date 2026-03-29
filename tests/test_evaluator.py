"""Tests for pilab.evaluator.agent — evaluation logic and verdict decisions."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pilab.evaluator.agent import _evaluate_finding


pytestmark = pytest.mark.asyncio


def _make_response(json_data, status_code=200):
    """Create a mock httpx.Response with .json() and .status_code."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _mock_client():
    """Mock httpx.AsyncClient where get/post/patch are async."""
    client = MagicMock()
    post_calls = []

    async def mock_get(url, **kwargs):
        if "/recent-titles" in url:
            return _make_response(["Prior Title 1", "Prior Title 2"])
        return _make_response({})

    async def mock_post(url, **kwargs):
        post_calls.append((url, kwargs.get("json", {})))
        return _make_response({"id": "test_id"}, 201)

    async def mock_patch(url, **kwargs):
        return _make_response({"status": "ok"})

    client.get = mock_get
    client.post = mock_post
    client.patch = mock_patch
    client._post_calls = post_calls
    return client


FINDING = {
    "id": "test_finding_id",
    "title": "New LLM Quantization Method",
    "summary": "A new way to quantize LLMs for edge devices.",
    "topic_tags": "ai,edge",
}


async def test_evaluate_approved():
    """High novelty + high feasibility → approved."""
    client = _mock_client()
    with patch("pilab.evaluator.agent.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            {"novelty_score": 8, "novelty_reasoning": "Very novel"},
            {
                "pi_feasibility_score": 9, "ram_estimate_gb": 4.0,
                "requires_gpu": False, "feasibility_notes": "Fits fine",
                "reason_code": None,
            },
        ]
        await _evaluate_finding(client, FINDING)

    # Should have posted: evaluation, project, finding status patch, event (x2)
    post_urls = [url for url, _ in client._post_calls]
    assert any("/evaluations" in u for u in post_urls)
    assert any("/projects" in u for u in post_urls)
    assert any("/events" in u for u in post_urls)


async def test_evaluate_rejected_gpu():
    """requires_gpu=True → rejected."""
    client = _mock_client()
    with patch("pilab.evaluator.agent.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            {"novelty_score": 8, "novelty_reasoning": "Novel"},
            {
                "pi_feasibility_score": 1, "ram_estimate_gb": 16.0,
                "requires_gpu": True, "feasibility_notes": "Needs CUDA",
                "reason_code": "requires_gpu",
            },
        ]
        await _evaluate_finding(client, FINDING)

    post_urls = [url for url, _ in client._post_calls]
    assert any("/rejections" in u for u in post_urls)
    assert not any("/projects" in u for u in post_urls)


async def test_evaluate_rejected_not_novel():
    """novelty_score <= 3 → rejected as not_novel."""
    client = _mock_client()
    with patch("pilab.evaluator.agent.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            {"novelty_score": 2, "novelty_reasoning": "Already known"},
            {
                "pi_feasibility_score": 8, "ram_estimate_gb": 2.0,
                "requires_gpu": False, "feasibility_notes": "Easy",
                "reason_code": None,
            },
        ]
        await _evaluate_finding(client, FINDING)

    post_urls = [url for url, _ in client._post_calls]
    assert any("/rejections" in u for u in post_urls)
    # Check reason_code
    rejection_data = next(d for u, d in client._post_calls if "/rejections" in u)
    assert rejection_data["reason_code"] == "not_novel"


async def test_evaluate_rejected_low_priority():
    """novelty<=5 AND feasibility<=5 → rejected as low_priority."""
    client = _mock_client()
    with patch("pilab.evaluator.agent.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            {"novelty_score": 4, "novelty_reasoning": "Incremental"},
            {
                "pi_feasibility_score": 4, "ram_estimate_gb": 6.0,
                "requires_gpu": False, "feasibility_notes": "Marginal",
                "reason_code": None,
            },
        ]
        await _evaluate_finding(client, FINDING)

    post_urls = [url for url, _ in client._post_calls]
    assert any("/rejections" in u for u in post_urls)
    rejection_data = next(d for u, d in client._post_calls if "/rejections" in u)
    assert rejection_data["reason_code"] == "low_priority"


async def test_evaluate_llm_failure_raises():
    """LLM call failure should propagate."""
    client = _mock_client()
    with patch("pilab.evaluator.agent.call_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = RuntimeError("LLM down")
        with pytest.raises(RuntimeError):
            await _evaluate_finding(client, FINDING)
