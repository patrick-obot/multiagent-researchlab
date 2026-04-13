"""PiLab centralised configuration.

All tunables live here so agents, API, and dashboard can be reconfigured
without touching business logic.  Override any value via environment
variables prefixed with ``PILAB_`` (e.g. ``PILAB_DB_PATH``).
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str) -> str:
    return os.environ.get(f"PILAB_{key}", default)


def _env_int(key: str, default: int) -> int:
    return int(_env(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(_env(key, str(default)))


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_PATH: str = _env("DB_PATH", "/mnt/pilab/pilab.db")
DB_BUSY_TIMEOUT_MS: int = _env_int("DB_BUSY_TIMEOUT_MS", 10_000)

# ---------------------------------------------------------------------------
# Central API (runs on mypi, all agents talk to this)
# ---------------------------------------------------------------------------

API_HOST: str = _env("API_HOST", "0.0.0.0")
API_PORT: int = _env_int("API_PORT", 8000)
API_BASE_URL: str = _env("API_BASE_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# LLM servers (Ollama on Mac Mini, or llama.cpp for Pi cluster benchmarking)
# ---------------------------------------------------------------------------

LLM_SCOUT_URL: str = _env("LLM_SCOUT_URL", "http://localhost:11434")
LLM_EVALUATOR_URL: str = _env("LLM_EVALUATOR_URL", "http://localhost:11434")
LLM_PLANNER_URL: str = _env("LLM_PLANNER_URL", "http://localhost:11434")

LLM_SCOUT_MODEL: str = _env("LLM_SCOUT_MODEL", "phi3:mini")
LLM_EVALUATOR_MODEL: str = _env("LLM_EVALUATOR_MODEL", "qwen2.5:14b")
LLM_PLANNER_MODEL: str = _env("LLM_PLANNER_MODEL", "mistral:7b")

LLM_RETRY_ATTEMPTS: int = _env_int("LLM_RETRY_ATTEMPTS", 3)
LLM_RETRY_BACKOFF_BASE: float = _env_float("LLM_RETRY_BACKOFF_BASE", 2.0)
LLM_REQUEST_TIMEOUT: float = _env_float("LLM_REQUEST_TIMEOUT", 120.0)

# ---------------------------------------------------------------------------
# Scout — poll intervals (seconds)
# ---------------------------------------------------------------------------

SCOUT_INTERVAL_HN: int = _env_int("SCOUT_INTERVAL_HN", 7200)           # 2h
SCOUT_INTERVAL_GITHUB: int = _env_int("SCOUT_INTERVAL_GITHUB", 7200)
SCOUT_INTERVAL_ARXIV: int = _env_int("SCOUT_INTERVAL_ARXIV", 21600)    # 6h
SCOUT_INTERVAL_RSS: int = _env_int("SCOUT_INTERVAL_RSS", 21600)
SCOUT_INTERVAL_REDDIT: int = _env_int("SCOUT_INTERVAL_REDDIT", 21600)
SCOUT_INTERVAL_YOUTUBE: int = _env_int("SCOUT_INTERVAL_YOUTUBE", 86400)  # 24h
SCOUT_INTERVAL_RELEASES: int = _env_int("SCOUT_INTERVAL_RELEASES", 86400)
SCOUT_INTERVAL_TELCO: int = _env_int("SCOUT_INTERVAL_TELCO", 86400)

SCOUT_STARTUP_JITTER_MAX: int = _env_int("SCOUT_STARTUP_JITTER_MAX", 300)  # 0-5 min random jitter
SCOUT_LLM_CONCURRENCY: int = _env_int("SCOUT_LLM_CONCURRENCY", 2)         # Ollama handles concurrent requests
SCOUT_HN_TOP_N: int = _env_int("SCOUT_HN_TOP_N", 30)

# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

EVALUATOR_POLL_INTERVAL: int = _env_int("EVALUATOR_POLL_INTERVAL", 60)
EVALUATOR_JOB_CLAIM_TIMEOUT: int = _env_int("EVALUATOR_JOB_CLAIM_TIMEOUT", 600)  # 10 min

# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

PLANNER_MONITOR_INTERVAL: int = _env_int("PLANNER_MONITOR_INTERVAL", 1800)  # 30 min

# ---------------------------------------------------------------------------
# Agent heartbeat
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL: int = _env_int("HEARTBEAT_INTERVAL", 60)
HEARTBEAT_OFFLINE_THRESHOLD: int = _env_int("HEARTBEAT_OFFLINE_THRESHOLD", 180)  # 3 min

# ---------------------------------------------------------------------------
# Topic keywords (used by scout filter)
# ---------------------------------------------------------------------------

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "ai": [
        "llm", "transformer", "inference", "quantization", "gguf", "llama",
        "mistral", "gemma", "turboquant", "karpathy", "huggingface",
        "diffusion", "embedding", "moe", "speculative decoding",
        "vision language", "multimodal",
    ],
    "telco": [
        "5g", "ran", "ai-ran", "o-ran", "mec", "edge computing",
        "network slicing", "telco", "gsma", "baseband", "open ran",
    ],
    "fintech": [
        "agentic commerce", "payments", "defi", "fraud detection",
        "open banking", "embedded finance", "stablecoin", "cbdc",
    ],
    "edge": [
        "raspberry pi", "arm", "embedded", "iot", "tinyml", "on-device",
        "local inference", "sbc", "jetson", "llama.cpp", "exo", "ollama",
    ],
}

# ---------------------------------------------------------------------------
# Scout sources — RSS / watched repos / subreddits / YouTube channels
# ---------------------------------------------------------------------------

RSS_FEEDS: list[str] = [
    "https://blog.research.google/feeds/posts/default",
    "https://huggingface.co/blog/feed.xml",
    "https://ai.meta.com/blog/rss/",
]

TELCO_RSS_FEEDS: list[str] = [
    "https://www.gsma.com/newsroom/feed/",
    "https://www.o-ran.org/feed",
]

REDDIT_SUBREDDITS: list[str] = ["LocalLLaMA", "MachineLearning"]

YOUTUBE_CHANNEL_IDS: list[str] = [
    # ByteMonk, Two Minute Papers — replace with actual channel IDs
]

GITHUB_WATCHED_REPOS: list[str] = [
    "ggml-org/llama.cpp",
    "exo-explore/exo",
    "ollama/ollama",
    "ml-explore/mlx",
]

ARXIV_CATEGORIES: list[str] = ["cs.LG", "cs.AI", "cs.NI"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = _env("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s [%(name)s] %(levelname)s %(message)s"

# ---------------------------------------------------------------------------
# Summariser prompts
# ---------------------------------------------------------------------------

SCOUT_SUMMARISE_SYSTEM: str = (
    "Summarise in exactly 3 sentences: "
    "(1) what it is and what problem it solves, "
    "(2) why relevant to AI/Fintech/Telco/Edge, "
    "(3) any technical details indicating hardware requirements. "
    "Be concise."
)
SCOUT_SUMMARISE_MAX_TOKENS: int = 200
SCOUT_SUMMARISE_TEMPERATURE: float = 0.1

# ---------------------------------------------------------------------------
# Evaluator prompts
# ---------------------------------------------------------------------------

EVALUATOR_NOVELTY_SYSTEM: str = (
    "Score novelty 1-10 vs recent history. "
    "1-3=known, 4-6=incremental, 7-9=novel, 10=breakthrough. "
    'Return JSON: {"novelty_score": int, "novelty_reasoning": str}'
)
EVALUATOR_NOVELTY_MAX_TOKENS: int = 300
EVALUATOR_NOVELTY_TEMPERATURE: float = 0.1

EVALUATOR_FEASIBILITY_SYSTEM: str = (
    "Assess against our hardware capabilities. "
    "Primary target: Mac Mini M4 16GB unified memory, Apple Silicon GPU, "
    "MLX/Ollama inference, ~40 tok/s for 7B Q4, ~15 tok/s for 14B Q4. "
    "Secondary target (benchmarking only): 3x Raspberry Pi 5, 8GB each, "
    "ARM aarch64, no GPU, ~15 tok/s for 7B Q4. "
    "Hard fail (score 1): requires NVIDIA CUDA specifically, needs >14GB RAM, "
    "closed weights, needs internet at inference. "
    "Return JSON: "
    '{"pi_feasibility_score": int, "ram_estimate_gb": float, '
    '"requires_gpu": bool, "feasibility_notes": str, "reason_code": str|null}. '
    "reason_code one of: requires_gpu, ram_exceeded, no_arm_support, "
    "closed_source, not_reproducible, too_slow, null."
)
EVALUATOR_FEASIBILITY_MAX_TOKENS: int = 400
EVALUATOR_FEASIBILITY_TEMPERATURE: float = 0.1

# ---------------------------------------------------------------------------
# Planner prompts
# ---------------------------------------------------------------------------

PLANNER_MILESTONES_SYSTEM: str = (
    "Generate 3-7 milestones as a JSON array. Rules: "
    "each completable in 1-3 days, clear done_condition, "
    "first milestone = environment setup, last = document learnings. "
    "Categories: setup|research|implementation|testing|benchmarking|documentation. "
    'Each object: {"sequence": int, "title": str, "description": str, '
    '"done_condition": str, "category": str, "estimated_days": int}. '
    "Respond with ONLY the raw JSON array. No preamble, no explanation, "
    "no markdown code fences. Start your response with [ and end with ]."
)
PLANNER_MILESTONES_MAX_TOKENS: int = 1500
PLANNER_MILESTONES_TEMPERATURE: float = 0.3

PLANNER_LEARNING_SYSTEM: str = (
    "Write a 2-4 sentence technical learning note. "
    "Be specific — prefer measurements over vague statements. "
    'Return JSON: {"category": str, "note": str}. '
    "Categories: hardware|model|networking|unexpected|process."
)
PLANNER_LEARNING_MAX_TOKENS: int = 200
PLANNER_LEARNING_TEMPERATURE: float = 0.4
