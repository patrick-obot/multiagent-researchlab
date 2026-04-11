"""Scout agent — asyncio main loop that polls sources and creates findings.

Runs on Mac Mini M4.  Communicates with the central API via HTTP.
"""

from __future__ import annotations

import asyncio
import logging
import random
import signal
from dataclasses import dataclass
from typing import Callable, Awaitable

import httpx

from pilab import config
from pilab.scout import dedup, filter as topic_filter, summariser
from pilab.scout.sources import hackernews, arxiv, github, reddit, rss, youtube
from pilab.shared.ulid import new_ulid

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
log = logging.getLogger(__name__)


@dataclass
class RawItem:
    title: str
    url: str
    raw_content: str
    source_type: str


# -------------------------------------------------------------------
# Source registry
# -------------------------------------------------------------------

@dataclass
class SourceDef:
    name: str
    fetch: Callable[[], Awaitable[list]]
    interval: int


SOURCES: list[SourceDef] = [
    SourceDef("hackernews", hackernews.fetch, config.SCOUT_INTERVAL_HN),
    SourceDef("github_trending", github.fetch_trending, config.SCOUT_INTERVAL_GITHUB),
    SourceDef("arxiv", arxiv.fetch, config.SCOUT_INTERVAL_ARXIV),
    SourceDef("rss", rss.fetch_general, config.SCOUT_INTERVAL_RSS),
    SourceDef("reddit", reddit.fetch, config.SCOUT_INTERVAL_REDDIT),
    SourceDef("youtube", youtube.fetch, config.SCOUT_INTERVAL_YOUTUBE),
    SourceDef("github_releases", github.fetch_releases, config.SCOUT_INTERVAL_RELEASES),
    SourceDef("telco_rss", rss.fetch_telco, config.SCOUT_INTERVAL_TELCO),
]

# -------------------------------------------------------------------
# Pipeline
# -------------------------------------------------------------------

# Semaphore ensures only N concurrent LLM calls (llama.cpp serves 1 at a time)
_llm_sem = asyncio.Semaphore(config.SCOUT_LLM_CONCURRENCY)
_shutdown = asyncio.Event()


async def _process_item(item: RawItem) -> None:
    """Run the full pipeline for a single raw item."""
    # 1. Dedup
    if await dedup.is_seen(item.url):
        return

    # 2. Topic filter
    text = f"{item.title} {item.raw_content}"
    topics = topic_filter.match_topics(text)
    if not topics:
        return

    topic_tags = ",".join(sorted(set(topics)))

    # 3. Summarise (rate-limited)
    async with _llm_sem:
        try:
            summary = await summariser.summarise(item.title, item.raw_content)
        except Exception:
            log.error("Summarisation failed for %s", item.title[:60], exc_info=True)
            summary = None

    # 4. Post finding to API
    finding_id = new_ulid()
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{config.API_BASE_URL}/findings",
            json={
                "id": finding_id,
                "title": item.title,
                "summary": summary,
                "source_type": item.source_type,
                "source_url": item.url,
                "topic_tags": topic_tags,
                "raw_content": item.raw_content[:5000],
                "scout_pi": "pi2",
                "status": "scouted",
            },
        )

        # 5. Mark URL seen
        await dedup.mark_seen(item.url)

        # 6. Enqueue for evaluator
        await client.post(
            f"{config.API_BASE_URL}/jobs",
            json={"finding_id": finding_id},
        )

        # 7. Log event
        await client.post(
            f"{config.API_BASE_URL}/events",
            json={
                "agent_name": "scout",
                "event_type": "new_finding",
                "entity_id": finding_id,
                "message": f"Scouted: {item.title[:80]}",
            },
        )

    log.info("Scouted: %s [%s]", item.title[:60], topic_tags)


async def _poll_source(source: SourceDef) -> None:
    """Poll a single source and process all items."""
    # Startup jitter
    jitter = random.uniform(0, config.SCOUT_STARTUP_JITTER_MAX)
    log.info("Source %s: starting in %.0fs (jitter)", source.name, jitter)
    await asyncio.sleep(jitter)

    while not _shutdown.is_set():
        log.info("Polling source: %s", source.name)
        try:
            raw_items = await source.fetch()
            log.info("Source %s returned %d items", source.name, len(raw_items))
            for item in raw_items:
                if _shutdown.is_set():
                    return
                try:
                    await _process_item(
                        RawItem(
                            title=item.title,
                            url=item.url,
                            raw_content=item.raw_content,
                            source_type=item.source_type,
                        )
                    )
                except Exception:
                    log.error(
                        "Failed to process item: %s", item.title[:60], exc_info=True
                    )
        except Exception:
            log.error("Failed to poll source %s", source.name, exc_info=True)

        # Wait for next poll interval (check shutdown periodically)
        for _ in range(source.interval // 10):
            if _shutdown.is_set():
                return
            await asyncio.sleep(10)


async def _heartbeat() -> None:
    """Send periodic heartbeat events to the API."""
    while not _shutdown.is_set():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{config.API_BASE_URL}/events",
                    json={
                        "agent_name": "scout",
                        "event_type": "heartbeat",
                        "message": "scout alive",
                    },
                )
        except Exception:
            log.warning("Heartbeat failed", exc_info=True)
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)


async def main() -> None:
    log.info("Scout agent starting — %d sources configured", len(SOURCES))

    # Handle SIGTERM for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown.set)

    tasks = [asyncio.create_task(_poll_source(s)) for s in SOURCES]
    tasks.append(asyncio.create_task(_heartbeat()))

    # Wait until shutdown is requested
    await _shutdown.wait()
    log.info("Shutdown requested, finishing current work...")

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("Scout agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
