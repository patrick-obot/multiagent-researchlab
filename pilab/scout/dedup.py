"""URL deduplication via SHA-256 hash checked against the central API."""

from __future__ import annotations

import hashlib

import httpx

from pilab import config


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


async def is_seen(url: str) -> bool:
    h = url_hash(url)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{config.API_BASE_URL}/seen-urls/{h}")
        resp.raise_for_status()
        return resp.json()["seen"]


async def mark_seen(url: str) -> None:
    h = url_hash(url)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{config.API_BASE_URL}/seen-urls", json={"hash": h}
        )
        resp.raise_for_status()
