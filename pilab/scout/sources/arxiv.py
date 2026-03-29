"""arXiv RSS feed source."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import feedparser

from pilab import config

log = logging.getLogger(__name__)


@dataclass
class RawItem:
    title: str
    url: str
    raw_content: str
    source_type: str = "arxiv"


async def fetch() -> list[RawItem]:
    items: list[RawItem] = []
    for cat in config.ARXIV_CATEGORIES:
        feed_url = f"https://rss.arxiv.org/rss/{cat}"
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                url = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                if url and title:
                    items.append(
                        RawItem(
                            title=title,
                            url=url,
                            raw_content=f"{title}\n{summary}",
                        )
                    )
        except Exception:
            log.error("Failed to fetch arXiv feed %s", cat, exc_info=True)
    return items
