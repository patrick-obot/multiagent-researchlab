"""Tests for scout source modules — verify data structure and error handling."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from pilab.scout.sources import arxiv, rss, youtube


pytestmark = pytest.mark.asyncio


def _mock_feed(entries):
    """Build a mock feedparser result with dict entries (supports .get())."""
    feed = MagicMock()
    feed.entries = entries
    return feed


# -------------------------------------------------------------------
# arXiv
# -------------------------------------------------------------------

class TestArxiv:
    async def test_fetch(self):
        entries = [{"title": "Paper Title", "link": "https://arxiv.org/abs/123", "summary": "Abstract"}]
        with patch("pilab.scout.sources.arxiv.config") as mock_config:
            mock_config.ARXIV_CATEGORIES = ["cs.LG"]
            with patch("pilab.scout.sources.arxiv.feedparser.parse", return_value=_mock_feed(entries)):
                items = await arxiv.fetch()
                assert len(items) == 1
                assert items[0].source_type == "arxiv"
                assert items[0].title == "Paper Title"

    async def test_fetch_empty(self):
        with patch("pilab.scout.sources.arxiv.config") as mock_config:
            mock_config.ARXIV_CATEGORIES = ["cs.LG"]
            with patch("pilab.scout.sources.arxiv.feedparser.parse", return_value=_mock_feed([])):
                items = await arxiv.fetch()
                assert items == []

    async def test_fetch_skips_missing_url(self):
        entries = [{"title": "No Link", "summary": "Abstract"}]
        with patch("pilab.scout.sources.arxiv.config") as mock_config:
            mock_config.ARXIV_CATEGORIES = ["cs.LG"]
            with patch("pilab.scout.sources.arxiv.feedparser.parse", return_value=_mock_feed(entries)):
                items = await arxiv.fetch()
                assert items == []


# -------------------------------------------------------------------
# RSS
# -------------------------------------------------------------------

class TestRss:
    async def test_fetch_general(self):
        entries = [{"title": "Blog Post", "link": "https://blog.example.com/1", "summary": "Summary"}]
        with patch("pilab.scout.sources.rss.config") as mock_config:
            mock_config.RSS_FEEDS = ["https://blog.example.com/feed"]
            with patch("pilab.scout.sources.rss.feedparser.parse", return_value=_mock_feed(entries)):
                items = await rss.fetch_general()
                assert len(items) == 1
                assert items[0].source_type == "rss"

    async def test_fetch_telco(self):
        entries = [{"title": "GSMA News", "link": "https://gsma.com/1", "summary": "News"}]
        with patch("pilab.scout.sources.rss.config") as mock_config:
            mock_config.TELCO_RSS_FEEDS = ["https://gsma.com/feed"]
            with patch("pilab.scout.sources.rss.feedparser.parse", return_value=_mock_feed(entries)):
                items = await rss.fetch_telco()
                assert len(items) == 1
                assert items[0].source_type == "telco_rss"

    async def test_fetch_general_empty(self):
        with patch("pilab.scout.sources.rss.config") as mock_config:
            mock_config.RSS_FEEDS = ["https://blog.example.com/feed"]
            with patch("pilab.scout.sources.rss.feedparser.parse", return_value=_mock_feed([])):
                items = await rss.fetch_general()
                assert items == []


# -------------------------------------------------------------------
# YouTube
# -------------------------------------------------------------------

class TestYouTube:
    async def test_fetch(self):
        entries = [{"title": "Video Title", "link": "https://youtube.com/watch?v=abc", "summary": "Desc"}]
        with patch("pilab.scout.sources.youtube.config") as mock_config:
            mock_config.YOUTUBE_CHANNEL_IDS = ["UC123"]
            with patch("pilab.scout.sources.youtube.feedparser.parse", return_value=_mock_feed(entries)):
                items = await youtube.fetch()
                assert len(items) == 1
                assert items[0].source_type == "youtube"

    async def test_fetch_empty_channels(self):
        with patch("pilab.scout.sources.youtube.config") as mock_config:
            mock_config.YOUTUBE_CHANNEL_IDS = []
            items = await youtube.fetch()
            assert items == []
