"""Generic RSS feed source (Google Research, HuggingFace, Meta AI, Telco)."""

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
    source_type: str = "rss"


async def fetch_general() -> list[RawItem]:
    """Fetch items from general RSS feeds."""
    return _parse_feeds(config.RSS_FEEDS, "rss")


async def fetch_telco() -> list[RawItem]:
    """Fetch items from telco RSS feeds."""
    return _parse_feeds(config.TELCO_RSS_FEEDS, "telco_rss")


def _parse_feeds(feed_urls: list[str], source_type: str) -> list[RawItem]:
    items: list[RawItem] = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")[:500]
                if link and title:
                    items.append(
                        RawItem(
                            title=title,
                            url=link,
                            raw_content=f"{title}\n{summary}",
                            source_type=source_type,
                        )
                    )
        except Exception:
            log.error("Failed to parse RSS feed %s", url, exc_info=True)
    return items
