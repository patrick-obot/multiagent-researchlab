"""Summarise a finding using the scout LLM."""

from __future__ import annotations

from pilab import config
from pilab.shared.llm import call_llm


async def summarise(title: str, raw_content: str) -> str:
    """Return a 3-sentence summary of the given content."""
    user_prompt = f"Title: {title}\n\nContent:\n{raw_content[:2000]}"
    return await call_llm(
        config.LLM_SCOUT_URL,
        model=config.LLM_SCOUT_MODEL,
        system=config.SCOUT_SUMMARISE_SYSTEM,
        user=user_prompt,
        max_tokens=config.SCOUT_SUMMARISE_MAX_TOKENS,
        temperature=config.SCOUT_SUMMARISE_TEMPERATURE,
    )
