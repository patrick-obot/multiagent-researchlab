"""GitHub trending and watched releases source."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from pilab import config

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


@dataclass
class RawItem:
    title: str
    url: str
    raw_content: str
    source_type: str = "github"


async def fetch_trending() -> list[RawItem]:
    """Fetch trending repos via GitHub search (stars gained recently)."""
    items: list[RawItem] = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GITHUB_API}/search/repositories",
                params={
                    "q": "stars:>100 pushed:>2026-01-01",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 30,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            resp.raise_for_status()
            for repo in resp.json().get("items", []):
                items.append(
                    RawItem(
                        title=f"{repo['full_name']}: {repo.get('description', '')}",
                        url=repo["html_url"],
                        raw_content=f"{repo['full_name']}\n{repo.get('description', '')}\n"
                        f"Stars: {repo.get('stargazers_count', 0)} "
                        f"Language: {repo.get('language', 'unknown')}",
                    )
                )
    except Exception:
        log.error("Failed to fetch GitHub trending", exc_info=True)
    return items


async def fetch_releases() -> list[RawItem]:
    """Fetch latest releases from watched repos."""
    items: list[RawItem] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for repo in config.GITHUB_WATCHED_REPOS:
            try:
                resp = await client.get(
                    f"{GITHUB_API}/repos/{repo}/releases/latest",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                rel = resp.json()
                tag = rel.get("tag_name", "")
                body = rel.get("body", "")[:500]
                items.append(
                    RawItem(
                        title=f"{repo} {tag}",
                        url=rel.get("html_url", f"https://github.com/{repo}"),
                        raw_content=f"{repo} release {tag}\n{body}",
                    )
                )
            except Exception:
                log.warning("Failed to fetch release for %s", repo, exc_info=True)
    return items
