"""Milestone generation for approved projects."""

from __future__ import annotations

import logging

import httpx

from pilab import config
from pilab.shared.llm import call_json
from pilab.shared.ulid import new_ulid

log = logging.getLogger(__name__)

API = config.API_BASE_URL


async def generate_milestones(client: httpx.AsyncClient, project: dict) -> None:
    """Generate milestones for a newly approved project via LLM."""
    project_id = project["id"]
    finding_id = project["finding_id"]

    # Load finding and evaluation for context
    resp = await client.get(f"{API}/findings/{finding_id}")
    resp.raise_for_status()
    finding = resp.json()

    eval_resp = await client.get(f"{API}/evaluations/{finding_id}")
    evaluation = eval_resp.json() if eval_resp.status_code == 200 else {}

    user_prompt = (
        f"Project: {project['title']}\n"
        f"Finding summary: {finding.get('summary', '')}\n"
        f"Topics: {finding.get('topic_tags', '')}\n"
        f"Feasibility notes: {evaluation.get('feasibility_notes', '')}\n"
        f"RAM estimate: {evaluation.get('ram_estimate_gb', 'unknown')} GB\n"
    )

    milestones = await call_json(
        config.LLM_PLANNER_URL,
        model=config.LLM_PLANNER_MODEL,
        system=config.PLANNER_MILESTONES_SYSTEM,
        user=user_prompt,
        max_tokens=config.PLANNER_MILESTONES_MAX_TOKENS,
        temperature=config.PLANNER_MILESTONES_TEMPERATURE,
    )

    # Defensive unwrap: if the model returns {"milestones": [...]} instead
    # of the bare array, accept the inner list. Same for any single list value.
    if isinstance(milestones, dict):
        list_values = [v for v in milestones.values() if isinstance(v, list)]
        if len(list_values) == 1:
            log.warning(
                "Planner LLM returned dict-wrapped milestones; unwrapping "
                "(keys=%s)", list(milestones.keys()),
            )
            milestones = list_values[0]

    if not isinstance(milestones, list):
        log.error(
            "Expected list of milestones, got %s; payload=%r",
            type(milestones).__name__,
            str(milestones)[:300],
        )
        return

    for ms in milestones:
        await client.post(f"{API}/milestones", json={
            "id": new_ulid(),
            "project_id": project_id,
            "sequence": int(ms.get("sequence", 0)),
            "title": ms.get("title", "Untitled"),
            "description": ms.get("description"),
            "done_condition": ms.get("done_condition"),
            "category": ms.get("category"),
            "estimated_days": int(ms.get("estimated_days", 1)),
            "status": "pending",
        })

    # Update project status
    await client.patch(
        f"{API}/projects/{project_id}/status",
        json={"status": "in_progress"},
    )

    await client.post(f"{API}/events", json={
        "agent_name": "planner",
        "event_type": "milestones_created",
        "entity_id": project_id,
        "message": f"Created {len(milestones)} milestones for: {project['title'][:60]}",
    })

    log.info("Created %d milestones for project %s", len(milestones), project_id)
