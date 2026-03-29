"""Reddit source using public JSON API (no auth required)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from pilab import config

log = logging.getLogger(__name__)


@dataclass
class RawItem:
    title: str
    url: str
    raw_content: str
    source_type: str = "reddit"


async def fetch() -> list[RawItem]:
    items: list[RawItem] = []
    headers = {"User-Agent": "PiLab/0.1 (research pipeline)"}
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for sub in config.REDDIT_SUBREDDITS:
            try:
                resp = await client.get(
                    f"https://www.reddit.com/r/{sub}/hot.json",
                    params={"limit": 25},
                )
                resp.raise_for_status()
                posts = resp.json().get("data", {}).get("children", [])
                for post in posts:
                    d = post.get("data", {})
                    title = d.get("title", "")
                    url = d.get("url", "")
                    selftext = d.get("selftext", "")[:500]
                    permalink = f"https://www.reddit.com{d.get('permalink', '')}"
                    if title:
                        items.append(
                            RawItem(
                                title=title,
                                url=url or permalink,
                                raw_content=f"{title}\n{selftext}",
                            )
                        )
            except Exception:
                log.error("Failed to fetch r/%s", sub, exc_info=True)
    return items
