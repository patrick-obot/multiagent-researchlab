"""Hacker News top stories source."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from pilab import config

log = logging.getLogger(__name__)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


@dataclass
class RawItem:
    title: str
    url: str
    raw_content: str
    source_type: str = "hackernews"


async def fetch() -> list[RawItem]:
    items: list[RawItem] = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(HN_TOP)
            resp.raise_for_status()
            story_ids = resp.json()[: config.SCOUT_HN_TOP_N]

            for sid in story_ids:
                try:
                    r = await client.get(HN_ITEM.format(sid))
                    r.raise_for_status()
                    data = r.json()
                    if not data or not data.get("url"):
                        continue
                    items.append(
                        RawItem(
                            title=data.get("title", ""),
                            url=data["url"],
                            raw_content=data.get("title", ""),
                        )
                    )
                except Exception:
                    log.warning("Failed to fetch HN item %s", sid, exc_info=True)
    except Exception:
        log.error("Failed to fetch HN top stories", exc_info=True)
    return items
