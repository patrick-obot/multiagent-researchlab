"""ULID generation helper."""

from __future__ import annotations

from ulid import ULID


def new_ulid() -> str:
    """Return a new ULID as a lowercase string."""
    return str(ULID())
