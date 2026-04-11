"""Planner agent — planning mode + monitor mode.

Runs on Mac Mini M4.  Uses Mistral 7B via Ollama for milestone generation
and learning note creation.
"""

from __future__ import annotations

import asyncio
import logging
import signal

import httpx

from pilab import config
from pilab.planner.planning import generate_milestones
from pilab.planner.monitor import check_milestones

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
log = logging.getLogger(__name__)

_shutdown = asyncio.Event()
_planning_lock = asyncio.Lock()

API = config.API_BASE_URL


async def _planning_loop() -> None:
    """Watch for approved projects and generate milestones."""
    async with httpx.AsyncClient(timeout=60) as client:
        while not _shutdown.is_set():
            try:
                resp = await client.get(
                    f"{API}/projects", params={"status": "approved"}
                )
                resp.raise_for_status()
                projects = resp.json()

                for project in projects:
                    if _shutdown.is_set():
                        return
                    async with _planning_lock:
                        try:
                            await generate_milestones(client, project)
                        except Exception:
                            log.error(
                                "Failed to plan project %s",
                                project["id"],
                                exc_info=True,
                            )
            except Exception:
                log.error("Planning loop error", exc_info=True)

            # Poll every 30 seconds for new approved projects
            for _ in range(3):
                if _shutdown.is_set():
                    return
                await asyncio.sleep(10)


async def _monitor_loop() -> None:
    """Periodically check milestones and generate learning notes."""
    async with httpx.AsyncClient(timeout=60) as client:
        while not _shutdown.is_set():
            async with _planning_lock:
                try:
                    await check_milestones(client)
                except Exception:
                    log.error("Monitor loop error", exc_info=True)

            # Wait for next monitor interval
            for _ in range(config.PLANNER_MONITOR_INTERVAL // 10):
                if _shutdown.is_set():
                    return
                await asyncio.sleep(10)


async def _heartbeat() -> None:
    while not _shutdown.is_set():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{API}/events", json={
                    "agent_name": "planner",
                    "event_type": "heartbeat",
                    "message": "planner alive",
                })
        except Exception:
            log.warning("Heartbeat failed", exc_info=True)
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)


async def main() -> None:
    log.info("Planner agent starting")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown.set)

    tasks = [
        asyncio.create_task(_planning_loop()),
        asyncio.create_task(_monitor_loop()),
        asyncio.create_task(_heartbeat()),
    ]

    await _shutdown.wait()
    log.info("Shutdown requested, finishing current work...")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("Planner agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
