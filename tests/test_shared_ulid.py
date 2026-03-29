"""Tests for pilab.shared.ulid."""

from pilab.shared.ulid import new_ulid


def test_new_ulid_is_string():
    u = new_ulid()
    assert isinstance(u, str)
    assert len(u) == 26  # ULID standard length


def test_new_ulid_unique():
    ids = {new_ulid() for _ in range(100)}
    assert len(ids) == 100
