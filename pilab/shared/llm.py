"""LLM HTTP client with JSON repair, retry, and structured output.

Talks to an OpenAI-compatible endpoint (Ollama, llama.cpp, etc.).  The main
entry point is :func:`call_json` which sends a chat-completion request and
returns the parsed JSON object, handling common LLM output quirks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from pilab import config

log = logging.getLogger(__name__)


# -------------------------------------------------------------------
# JSON repair helpers
# -------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that models love to add."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        text = re.sub(r"^```\w*\s*\n?", "", text)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _fix_trailing_commas(text: str) -> str:
    """Remove trailing commas before } or ]."""
    return re.sub(r",\s*([}\]])", r"\1", text)


def _extract_json_object(text: str) -> str | None:
    """Try to extract the outermost { ... } or [ ... ] from the text.

    Uses the opener that appears *first* in the text so that arrays of
    objects (which contain nested `{`) don't get mis-extracted as the
    first inner object.
    """
    brace_pos = text.find("{")
    bracket_pos = text.find("[")

    candidates: list[tuple[int, str, str]] = []
    if brace_pos != -1:
        candidates.append((brace_pos, "{", "}"))
    if bracket_pos != -1:
        candidates.append((bracket_pos, "[", "]"))
    if not candidates:
        return None

    # Whichever opener appears first in the string is the outer structure.
    candidates.sort()
    start, opener, closer = candidates[0]

    depth = 0
    for i in range(start, len(text)):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def repair_json(raw: str) -> Any:
    """Best-effort parse of LLM output as JSON.

    Attempts, in order:
    1. Direct ``json.loads``
    2. Strip markdown fences → parse
    3. Fix trailing commas → parse
    4. Regex-extract first JSON object/array → parse
    5. Raise ``ValueError``
    """
    # 1. Try raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Strip fences
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Fix trailing commas
    fixed = _fix_trailing_commas(cleaned)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 4. Extract first JSON object/array
    extracted = _extract_json_object(raw)
    if extracted:
        try:
            return json.loads(_fix_trailing_commas(extracted))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM output: {raw[:200]!r}")


# -------------------------------------------------------------------
# HTTP client
# -------------------------------------------------------------------

async def call_llm(
    base_url: str,
    *,
    model: str | None = None,
    system: str,
    user: str,
    max_tokens: int = 256,
    temperature: float = 0.1,
) -> str:
    """Send a chat-completion request and return the raw text response.

    Retries on HTTP 503 (server busy) with exponential backoff.
    """
    url = f"{base_url}/v1/chat/completions"
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if model is not None:
        payload["model"] = model

    last_exc: Exception | None = None
    for attempt in range(config.LLM_RETRY_ATTEMPTS):
        try:
            async with httpx.AsyncClient(
                timeout=config.LLM_REQUEST_TIMEOUT
            ) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 503:
                    raise httpx.HTTPStatusError(
                        "Server busy", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                log.debug(
                    "LLM response (%s, attempt %d): %s",
                    base_url, attempt + 1, content[:100],
                )
                return content
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            last_exc = exc
            delay = config.LLM_RETRY_BACKOFF_BASE ** attempt
            log.warning(
                "LLM call to %s failed (attempt %d/%d): %s — retrying in %.1fs",
                base_url, attempt + 1, config.LLM_RETRY_ATTEMPTS, exc, delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"LLM call to {base_url} failed after {config.LLM_RETRY_ATTEMPTS} attempts"
    ) from last_exc


async def call_json(
    base_url: str,
    *,
    model: str | None = None,
    system: str,
    user: str,
    max_tokens: int = 256,
    temperature: float = 0.1,
) -> Any:
    """Send a chat-completion request and return the parsed JSON object.

    Combines :func:`call_llm` with :func:`repair_json`.
    """
    raw = await call_llm(
        base_url,
        model=model,
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return repair_json(raw)
