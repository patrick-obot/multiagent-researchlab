"""Keyword-based topic filter for scout items."""

from __future__ import annotations

from pilab import config


def match_topics(text: str) -> list[str]:
    """Return list of matching topic names for the given text.

    Matching is case-insensitive against the keyword lists in config.
    """
    lower = text.lower()
    matched: list[str] = []
    for topic, keywords in config.TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                matched.append(topic)
                break
    return matched
