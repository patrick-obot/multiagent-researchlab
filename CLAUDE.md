# PiLab — Claude Code Guide

## What is this?

Multi-agent research pipeline across 3 Raspberry Pi 5s (8GB each, ARM aarch64, no GPU).
Agents scout, evaluate, and plan AI/Telco/Fintech/Edge research using local LLMs via llama.cpp.

## Hardware

| Host | Role | LLM | Port | Storage |
|------|------|-----|------|---------|
| mypi | Evaluator + API + DB | Qwen 2.5 7B Q4 | 8081 | 1TB NVMe |
| pi2 | Scout | Phi-3 Mini Q4 | 8080 | 256GB SSD |
| pi3 | Planner + Dashboard | Phi-3 Mini Q4 | 8082 | 256GB SSD |

## Architecture

- Central FastAPI on mypi (port 8000) owns the SQLite DB — all agents talk to it via HTTP
- No NFS/shared filesystem — everything goes through the API
- llama.cpp in server mode on each Pi, one model per Pi
- Config via env vars prefixed `PILAB_` (see `pilab/config.py`)

## Project layout

```
pilab/
├── config.py           # All tunables (env-overridable)
├── db/schema.sql       # SQLite schema (ULIDs, UTC ISO 8601)
├── db/store.py         # Typed async DB helpers (aiosqlite)
├── db/migrate.py       # Forward-only migration runner
├── shared/llm.py       # llama.cpp HTTP client + JSON repair
├── shared/queue.py     # Job queue convenience wrappers
├── shared/ulid.py      # ULID generation
├── scout/              # Scout agent (runs on pi2)
├── evaluator/          # Evaluator agent (runs on mypi)
├── planner/            # Planner agent (runs on pi3)
├── api/main.py         # FastAPI central data API
├── dashboard/          # Vanilla JS web dashboard
└── deploy/             # systemd unit files
```

## Dev commands

```bash
# Activate venv
source .venv/bin/activate

# Run tests (116 tests, ~3s)
python -m pytest tests/ -v

# Run API locally (dev mode)
uvicorn pilab.api.main:app --reload --port 8000

# Run individual agents
python -m pilab.scout.agent
python -m pilab.evaluator.agent
python -m pilab.planner.agent

# Init DB manually
python -c "import asyncio; from pilab.db.store import open_db; asyncio.run(open_db('/tmp/test.db'))"
```

## Service management (systemd)

```bash
# API is deployed as a systemd service on mypi (auto-restarts, starts on boot)
sudo systemctl status pilab-api
sudo systemctl restart pilab-api
journalctl -u pilab-api -f

# Other agents (when deployed to their respective Pis)
sudo systemctl status pilab-scout       # pi2
sudo systemctl status pilab-evaluator   # mypi
sudo systemctl status pilab-planner     # pi3
```

## Conventions

- All IDs are ULIDs (lowercase string) via `python-ulid`
- All timestamps are UTC ISO 8601 (`%Y-%m-%dT%H:%M:%SZ`)
- DB access is async via `aiosqlite`; all store functions take `db` as first arg
- LLM responses are parsed with `repair_json()` which handles markdown fences, trailing commas, etc.
- Agents communicate via HTTP to the central API, never directly to the DB
- Scout agent posts findings → evaluator claims jobs from queue → planner generates milestones
- Config is centralized in `pilab/config.py` with `_env()` helpers

## Testing

- Tests live in `tests/` using pytest + pytest-asyncio
- DB tests use in-memory SQLite (`:memory:`)
- HTTP calls are mocked with `httpx` mock transports or `unittest.mock.AsyncMock`
- No real LLM calls in tests — mock `call_json`/`call_llm`

## Key dependencies

python-ulid, aiosqlite, fastapi, uvicorn, httpx, feedparser, python-dateutil
Test deps: pytest, pytest-asyncio, httpx (TestClient)
