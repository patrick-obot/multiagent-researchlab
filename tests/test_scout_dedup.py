"""Tests for pilab.scout.dedup — URL deduplication."""

from pilab.scout.dedup import url_hash


def test_url_hash_deterministic():
    h1 = url_hash("https://example.com/article")
    h2 = url_hash("https://example.com/article")
    assert h1 == h2


def test_url_hash_different():
    h1 = url_hash("https://example.com/a")
    h2 = url_hash("https://example.com/b")
    assert h1 != h2


def test_url_hash_is_hex():
    h = url_hash("https://example.com")
    assert len(h) == 64  # SHA-256 hex digest
    assert all(c in "0123456789abcdef" for c in h)
