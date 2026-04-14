"""Evaluator agent — polls job queue and evaluates findings.

Runs on Mac Mini M4.  Uses Qwen 2.5 14B via Ollama for novelty scoring
and feasibility assessment.
"""

from __future__ import annotations

import asyncio
import logging
import signal

import httpx

from pilab import config
from pilab.shared.llm import call_json
from pilab.shared.ulid import new_ulid

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
log = logging.getLogger(__name__)

_shutdown = asyncio.Event()
API = config.API_BASE_URL


# -------------------------------------------------------------------
# API helpers
# -------------------------------------------------------------------

async def _api_get(client: httpx.AsyncClient, path: str, **params) -> dict | list | None:
    resp = await client.get(f"{API}{path}", params=params)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


async def _api_post(client: httpx.AsyncClient, path: str, json: dict) -> dict:
    resp = await client.post(f"{API}{path}", json=json)
    resp.raise_for_status()
    return resp.json()


async def _api_patch(client: httpx.AsyncClient, path: str, json: dict | None = None) -> dict:
    resp = await client.patch(f"{API}{path}", json=json or {})
    resp.raise_for_status()
    return resp.json()


# -------------------------------------------------------------------
# Evaluation logic
# -------------------------------------------------------------------

async def _evaluate_finding(client: httpx.AsyncClient, finding: dict) -> None:
    """Run novelty + feasibility LLM calls and record verdict."""
    finding_id = finding["id"]
    title = finding["title"]
    summary = finding.get("summary", "") or ""

    # Get recent titles for novelty context
    recent = await _api_get(client, "/recent-titles", limit=20) or []
    recent_ctx = "\n".join(f"- {t}" for t in recent) if recent else "(no prior findings)"

    # Call 1: Novelty scoring
    novelty_prompt = (
        f"New finding:\nTitle: {title}\nSummary: {summary}\n\n"
        f"Recent evaluated titles:\n{recent_ctx}"
    )
    try:
        novelty_result = await call_json(
            config.LLM_EVALUATOR_URL,
            model=config.LLM_EVALUATOR_MODEL,
            system=config.EVALUATOR_NOVELTY_SYSTEM,
            user=novelty_prompt,
            max_tokens=config.EVALUATOR_NOVELTY_MAX_TOKENS,
            temperature=config.EVALUATOR_NOVELTY_TEMPERATURE,
        )
    except Exception:
        log.error("Novelty scoring failed for %s", finding_id, exc_info=True)
        raise

    novelty_score = int(novelty_result.get("novelty_score", 5))

    # Call 2: Pi feasibility
    feasibility_prompt = (
        f"Title: {title}\nSummary: {summary}\n\n"
        f"Assess whether this can run on our lab hardware (Mac Mini M4 primary, Pi cluster for benchmarking)."
    )
    try:
        feasibility_result = await call_json(
            config.LLM_EVALUATOR_URL,
            model=config.LLM_EVALUATOR_MODEL,
            system=config.EVALUATOR_FEASIBILITY_SYSTEM,
            user=feasibility_prompt,
            max_tokens=config.EVALUATOR_FEASIBILITY_MAX_TOKENS,
            temperature=config.EVALUATOR_FEASIBILITY_TEMPERATURE,
        )
    except Exception:
        log.error("Feasibility assessment failed for %s", finding_id, exc_info=True)
        raise

    feasibility_score = int(feasibility_result.get("pi_feasibility_score", 5))
    ram_estimate = float(feasibility_result.get("ram_estimate_gb", 0))
    requires_gpu = bool(feasibility_result.get("requires_gpu", False))
    feasibility_notes = feasibility_result.get("feasibility_notes", "")
    reason_code = feasibility_result.get("reason_code")

    # Verdict logic
    if requires_gpu or feasibility_score <= 2:
        verdict = "rejected"
        verdict_reason = reason_code or "infeasible"
    elif novelty_score <= 3:
        verdict = "rejected"
        verdict_reason = "not_novel"
    elif novelty_score <= 5 and feasibility_score <= 5:
        verdict = "rejected"
        verdict_reason = "low_priority"
    else:
        verdict = "approved"
        verdict_reason = None

    # Record evaluation
    eval_id = new_ulid()
    await _api_post(client, "/evaluations", {
        "id": eval_id,
        "finding_id": finding_id,
        "novelty_score": novelty_score,
        "pi_feasibility_score": feasibility_score,
        "feasibility_notes": feasibility_notes,
        "ram_estimate_gb": ram_estimate,
        "requires_gpu": requires_gpu,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "evaluated_by": "evaluator",
    })

    if verdict == "approved":
        # Create project stub
        project_id = new_ulid()
        await _api_post(client, "/projects", {
            "id": project_id,
            "finding_id": finding_id,
            "evaluation_id": eval_id,
            "title": title,
            "status": "awaiting_approval",
            "topic_tags": finding.get("topic_tags"),
        })
        await _api_patch(client, f"/findings/{finding_id}/status", {"status": "approved"})
        await _api_post(client, "/events", {
            "agent_name": "evaluator",
            "event_type": "approved",
            "entity_id": finding_id,
            "message": f"Approved: {title[:80]} (novelty={novelty_score}, feasibility={feasibility_score})",
        })
        log.info("APPROVED: %s (n=%d, f=%d)", title[:60], novelty_score, feasibility_score)
    else:
        await _api_post(client, "/rejections", {
            "finding_id": finding_id,
            "evaluation_id": eval_id,
            "reason_code": verdict_reason,
            "reason_detail": f"novelty={novelty_score}, feasibility={feasibility_score}, "
                             f"gpu={requires_gpu}, notes={feasibility_notes[:200]}",
        })
        await _api_patch(client, f"/findings/{finding_id}/status", {"status": "rejected"})
        await _api_post(client, "/events", {
            "agent_name": "evaluator",
            "event_type": "rejected",
            "entity_id": finding_id,
            "message": f"Rejected ({verdict_reason}): {title[:60]}",
        })
        log.info("REJECTED (%s): %s (n=%d, f=%d)", verdict_reason, title[:60], novelty_score, feasibility_score)


# -------------------------------------------------------------------
# Main loop
# -------------------------------------------------------------------

async def _poll_loop() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        while not _shutdown.is_set():
            # Reap stale jobs first
            try:
                await _api_post(client, "/jobs/reap", {})
            except Exception:
                log.warning("Job reaping failed", exc_info=True)

            # Try to claim a job
            try:
                resp = await client.post(
                    f"{API}/jobs/claim", params={"claimed_by": "evaluator"}
                )
                if resp.status_code == 404:
                    # No pending jobs
                    await asyncio.sleep(config.EVALUATOR_POLL_INTERVAL)
                    continue
                resp.raise_for_status()
                job = resp.json()
            except Exception:
                log.warning("Job claim failed", exc_info=True)
                await asyncio.sleep(config.EVALUATOR_POLL_INTERVAL)
                continue

            # Fetch the finding
            finding = await _api_get(client, f"/findings/{job['finding_id']}")
            if not finding:
                log.error("Finding %s not found for job %s", job["finding_id"], job["id"])
                await _api_patch(client, f"/jobs/{job['id']}/fail?error_message=finding_not_found")
                continue

            # Mark the finding as being actively evaluated so it shows up in the
            # dashboard's Evaluating column while the LLM calls are running.
            # The approved/rejected transition inside _evaluate_finding will
            # move it out of this state a minute or so later.
            try:
                await _api_patch(
                    client, f"/findings/{finding['id']}/status",
                    {"status": "evaluating"},
                )
            except Exception:
                log.warning("Could not set finding to evaluating", exc_info=True)

            # Evaluate
            try:
                await _evaluate_finding(client, finding)
                await _api_patch(client, f"/jobs/{job['id']}/done")
            except Exception:
                log.error("Evaluation failed for job %s", job["id"], exc_info=True)
                try:
                    await _api_patch(client, f"/jobs/{job['id']}/fail?error_message=evaluation_error")
                except Exception:
                    pass


async def _heartbeat() -> None:
    while not _shutdown.is_set():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await _api_post(client, "/events", {
                    "agent_name": "evaluator",
                    "event_type": "heartbeat",
                    "message": "evaluator alive",
                })
        except Exception:
            log.warning("Heartbeat failed", exc_info=True)
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)


async def _reset_orphaned_evaluating() -> None:
    """Reset any findings stuck in 'evaluating' from a previous crash.

    If the evaluator died mid-LLM-call, the finding was flipped to
    'evaluating' but never transitioned to approved/rejected. Reset those
    back to 'scouted' on startup so the job queue's reaper picks them
    up and re-dispatches. Runs once at agent start.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            orphans = await _api_get(client, "/findings", status="evaluating") or []
        except Exception:
            log.warning("Startup orphan check failed", exc_info=True)
            return
        if not orphans:
            return
        log.info("Resetting %d orphaned 'evaluating' finding(s) to 'scouted'", len(orphans))
        for f in orphans:
            try:
                await _api_patch(
                    client, f"/findings/{f['id']}/status",
                    {"status": "scouted"},
                )
            except Exception:
                log.warning("Could not reset finding %s", f.get("id"), exc_info=True)


async def main() -> None:
    log.info("Evaluator agent starting")

    # Wait briefly for the API to be ready (launchd startup race protection
    # is in the plist wrapper, but this call happens after the wrapper exits).
    await _reset_orphaned_evaluating()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown.set)

    tasks = [
        asyncio.create_task(_poll_loop()),
        asyncio.create_task(_heartbeat()),
    ]

    await _shutdown.wait()
    log.info("Shutdown requested, finishing current work...")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("Evaluator agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
