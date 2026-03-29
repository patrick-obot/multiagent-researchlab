"""YouTube channel RSS feed source."""

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
    source_type: str = "youtube"


async def fetch() -> list[RawItem]:
    items: list[RawItem] = []
    for channel_id in config.YOUTUBE_CHANNEL_IDS:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "")[:300]
                if link and title:
                    items.append(
                        RawItem(
                            title=title,
                            url=link,
                            raw_content=f"{title}\n{summary}",
                        )
                    )
        except Exception:
            log.error(
                "Failed to fetch YouTube feed for %s", channel_id, exc_info=True
            )
    return items
