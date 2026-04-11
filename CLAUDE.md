# PiLab — Claude Code Guide

## What is this?

Multi-agent research pipeline running on a Mac Mini M4 (16GB) as the primary host,
with a 3x Raspberry Pi 5 cluster retained for distributed inference benchmarking.
Agents scout, evaluate, and plan AI/Telco/Fintech/Edge research using local LLMs via Ollama.

## Hardware

### Primary Host — Mac Mini M4

| Component | Spec |
|-----------|------|
| CPU/GPU | Apple M4 (unified memory, Apple Silicon GPU) |
| RAM | 16GB unified |
| Inference | Ollama (MLX-accelerated) |
| Roles | All agents + API + DB + Dashboard |

| Agent | Model | Ollama Tag |
|-------|-------|------------|
| Scout | Phi-3 Mini | `phi3:mini` |
| Evaluator | Qwen 2.5 14B | `qwen2.5:14b` |
| Planner | Mistral 7B | `mistral:7b` |

### Pi Cluster (benchmarking only)

| Host | Role | Port | Storage |
|------|------|------|---------|
| mypi | llama.cpp RPC master + exo node | 50052 | 1TB NVMe |
| pi2 | llama.cpp RPC worker | 50052 | 256GB SSD |
| pi3 | llama.cpp RPC worker | 50052 | 256GB SSD |

All Pis: Raspberry Pi 5, 8GB RAM, ARM aarch64, gigabit ethernet.

## Architecture

- All agents run on Mac Mini M4, single Ollama instance serves all models
- Central FastAPI (port 8000) owns the SQLite DB — agents talk to it via HTTP
- No NFS/shared filesystem — everything goes through the API
- Config via env vars prefixed `PILAB_` (see `pilab/config.py`)
- Pi cluster used only when a project milestone requires benchmarking

## Project layout

```
pilab/
├── config.py           # All tunables (env-overridable)
├── db/schema.sql       # SQLite schema (ULIDs, UTC ISO 8601)
├── db/store.py         # Typed async DB helpers (aiosqlite)
├── db/migrate.py       # Forward-only migration runner
├── shared/llm.py       # OpenAI-compatible LLM client + JSON repair
├── shared/queue.py     # Job queue convenience wrappers
├── shared/ulid.py      # ULID generation
├── scout/              # Scout agent
├── evaluator/          # Evaluator agent
├── planner/            # Planner agent
├── api/main.py         # FastAPI central data API
├── dashboard/          # Vanilla JS web dashboard
└── deploy/             # systemd unit files
```

## Dev commands

```bash
# Activate venv
source .venv/bin/activate

# Run tests (117 tests, ~3s)
python -m pytest tests/ -v

# Start Ollama (must be running before agents)
ollama serve

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
# All services run on the same machine
sudo systemctl status pilab-api
sudo systemctl status pilab-scout
sudo systemctl status pilab-evaluator
sudo systemctl status pilab-planner
journalctl -u pilab-api -f
```

## Conventions

- All IDs are ULIDs (lowercase string) via `python-ulid`
- All timestamps are UTC ISO 8601 (`%Y-%m-%dT%H:%M:%SZ`)
- DB access is async via `aiosqlite`; all store functions take `db` as first arg
- LLM responses are parsed with `repair_json()` which handles markdown fences, trailing commas, etc.
- Agents communicate via HTTP to the central API, never directly to the DB
- Scout agent posts findings → evaluator claims jobs from queue → planner generates milestones
- Config is centralized in `pilab/config.py` with `_env()` helpers
- LLM calls use OpenAI-compatible `/v1/chat/completions` endpoint (works with Ollama and llama.cpp)

## Testing

- Tests live in `tests/` using pytest + pytest-asyncio
- DB tests use in-memory SQLite (`:memory:`)
- HTTP calls are mocked with `httpx` mock transports or `unittest.mock.AsyncMock`
- No real LLM calls in tests — mock `call_json`/`call_llm`

## Key dependencies

python-ulid, aiosqlite, fastapi, uvicorn, httpx, feedparser, python-dateutil
Test deps: pytest, pytest-asyncio, httpx (TestClient)
