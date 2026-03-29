"""Monitor mode — check milestones and generate learning notes."""

from __future__ import annotations

import logging

import httpx

from pilab import config
from pilab.shared.llm import call_json
from pilab.shared.ulid import new_ulid

log = logging.getLogger(__name__)

API = config.API_BASE_URL


async def check_milestones(client: httpx.AsyncClient) -> None:
    """Scan in-progress projects for completed/blocked milestones needing learning notes."""
    resp = await client.get(f"{API}/projects", params={"status": "in_progress"})
    resp.raise_for_status()
    projects = resp.json()

    for project in projects:
        project_id = project["id"]

        ms_resp = await client.get(f"{API}/projects/{project_id}/milestones")
        ms_resp.raise_for_status()
        milestones = ms_resp.json()

        all_completed = True
        for ms in milestones:
            if ms["status"] not in ("completed", "blocked"):
                all_completed = False if ms["status"] != "completed" else all_completed
                continue

            # Check if we already have a learning for this milestone
            hl_resp = await client.get(f"{API}/milestones/{ms['id']}/has-learning")
            hl_resp.raise_for_status()
            if hl_resp.json()["has_learning"]:
                continue

            # Generate learning note
            try:
                user_prompt = (
                    f"Project: {project['title']}\n"
                    f"Milestone: {ms['title']}\n"
                    f"Description: {ms.get('description', '')}\n"
                    f"Status: {ms['status']}\n"
                    f"Done condition: {ms.get('done_condition', '')}\n"
                )
                result = await call_json(
                    config.LLM_PLANNER_URL,
                    system=config.PLANNER_LEARNING_SYSTEM,
                    user=user_prompt,
                    max_tokens=config.PLANNER_LEARNING_MAX_TOKENS,
                    temperature=config.PLANNER_LEARNING_TEMPERATURE,
                )

                await client.post(f"{API}/learnings", json={
                    "id": new_ulid(),
                    "project_id": project_id,
                    "milestone_id": ms["id"],
                    "category": result.get("category", "process"),
                    "note": result.get("note", ""),
                    "agent": "planner",
                })

                await client.post(f"{API}/events", json={
                    "agent_name": "planner",
                    "event_type": "learning_logged",
                    "entity_id": ms["id"],
                    "message": f"Learning for: {ms['title'][:60]}",
                })

                log.info("Logged learning for milestone %s", ms["id"])
            except Exception:
                log.error("Failed to generate learning for milestone %s", ms["id"], exc_info=True)

        # Check if all milestones are completed
        if milestones and all(m["status"] == "completed" for m in milestones):
            await client.patch(
                f"{API}/projects/{project_id}/status",
                json={"status": "completed"},
            )
            await client.post(f"{API}/events", json={
                "agent_name": "planner",
                "event_type": "project_completed",
                "entity_id": project_id,
                "message": f"Completed: {project['title'][:60]}",
            })
            log.info("Project %s completed", project_id)
