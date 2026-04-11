# PiLab — Multi-Agent Research Pipeline

A research pipeline using local LLMs via Ollama on a Mac Mini M4 to scout, evaluate, plan, and track AI/Telco/Fintech/Edge research. A 3x Raspberry Pi 5 cluster is available for distributed inference benchmarking.

## Architecture

```
Mac Mini M4 (16GB unified memory)
+---------------------------------------------------+
|  Ollama (MLX-accelerated)                         |
|  ┌──────────┐ ┌─────────────┐ ┌───────────────┐  |
|  │phi3:mini │ │qwen2.5:14b  │ │ mistral:7b    │  |
|  │(Scout)   │ │(Evaluator)  │ │ (Planner)     │  |
|  └────┬─────┘ └──────┬──────┘ └──────┬────────┘  |
|       │               │              │            |
|  ┌────┴───────────────┴──────────────┴────────┐   |
|  │  FastAPI (port 8000) + SQLite DB           │   |
|  │  Dashboard (vanilla JS)                    │   |
|  └────────────────────────────────────────────┘   |
+---------------------------------------------------+

Pi Cluster (benchmarking only, gigabit ethernet):
  mypi (RPC master + exo) ── pi2 (RPC worker) ── pi3 (RPC worker)
```

All agents run on the Mac Mini. Inter-agent communication goes through the central FastAPI (no NFS/shared filesystem).

## Pipeline Flow

1. **Scout** polls sources (HN, GitHub, arXiv, Reddit, RSS, YouTube) on configurable intervals
2. Findings are filtered by topic keywords (AI, Telco, Fintech, Edge) and summarised by Phi-3 Mini
3. **Evaluator** claims jobs from the queue, scores novelty + feasibility via Qwen 2.5 14B
4. Approved findings become projects; rejected ones are archived with reason codes
5. **Planner** generates milestones for approved projects via Mistral 7B
6. Dashboard shows the full pipeline state with live agent status

## Setup

### Prerequisites

```bash
# Install Ollama (https://ollama.com)
# Pull required models
ollama pull phi3:mini
ollama pull qwen2.5:14b
ollama pull mistral:7b

# Clone and install Python deps
cd /opt/pilab  # or your preferred location
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Start Services

```bash
# Start Ollama (if not already running)
ollama serve

# Start the API
uvicorn pilab.api.main:app --host 0.0.0.0 --port 8000

# Start agents (each in its own terminal, or use systemd)
python -m pilab.scout.agent
python -m pilab.evaluator.agent
python -m pilab.planner.agent
```

### systemd Deployment

```bash
sudo cp pilab/deploy/pilab-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pilab-api pilab-scout pilab-evaluator pilab-planner
```

### Dashboard

The dashboard is served from the FastAPI app at `http://localhost:8000/dashboard/`.
No separate server needed.

## Configuration

All settings can be overridden via environment variables prefixed with `PILAB_`.
See `pilab/config.py` for the full list. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PILAB_DB_PATH` | `/mnt/pilab/pilab.db` | SQLite database path |
| `PILAB_API_BASE_URL` | `http://localhost:8000` | Central API URL |
| `PILAB_LLM_SCOUT_URL` | `http://localhost:11434` | Scout LLM endpoint |
| `PILAB_LLM_EVALUATOR_URL` | `http://localhost:11434` | Evaluator LLM endpoint |
| `PILAB_LLM_PLANNER_URL` | `http://localhost:11434` | Planner LLM endpoint |
| `PILAB_LLM_SCOUT_MODEL` | `phi3:mini` | Scout model name |
| `PILAB_LLM_EVALUATOR_MODEL` | `qwen2.5:14b` | Evaluator model name |
| `PILAB_LLM_PLANNER_MODEL` | `mistral:7b` | Planner model name |
| `PILAB_LOG_LEVEL` | `INFO` | Logging level |

## Pi Cluster (Benchmarking)

The 3x Raspberry Pi 5 cluster (8GB each, ARM aarch64) is retained for distributed inference experiments. It uses llama.cpp RPC mode:

- **mypi** (1TB NVMe): RPC master + exo node
- **pi2** (256GB SSD): RPC worker on port 50052
- **pi3** (256GB SSD): RPC worker on port 50052

To use the Pi cluster for a benchmark, override the LLM URL for the relevant agent:
```bash
PILAB_LLM_EVALUATOR_URL=http://mypi:8081 python -m pilab.evaluator.agent
```

## Testing

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

117 tests covering all modules:
- DB store (34), migrations (4), shared modules (22)
- Scout filter/dedup/summariser/sources (20)
- Evaluator verdict logic (5), Planner milestones/monitor (5)
- API endpoints (23)

All tests use in-memory SQLite and mocked LLM/HTTP calls — no external services required.

## Monitoring

- Dashboard: `http://localhost:8000/dashboard/`
- Swagger docs: `http://localhost:8000/docs`
- Agent status pills show live/offline based on heartbeats (3-minute threshold)
- Agent events are logged to `agent_events` table and visible in the dashboard feed
- All agents log to stdout (captured by journald): `journalctl -u pilab-api -f`

## Project Structure

```
pilab/
├── config.py              # Centralized configuration
├── db/
│   ├── schema.sql         # Database schema
│   ├── store.py           # Typed DB helper functions
│   ├── migrate.py         # Schema migration runner
│   └── migrations/        # Numbered SQL migration files
├── shared/
│   ├── llm.py             # OpenAI-compatible LLM client with JSON repair
│   ├── queue.py           # Job queue helpers
│   └── ulid.py            # ULID generation
├── scout/
│   ├── agent.py           # Scout main loop
│   ├── filter.py          # Topic keyword filter
│   ├── dedup.py           # URL deduplication
│   ├── summariser.py      # LLM summarization
│   └── sources/           # Individual source fetchers
├── evaluator/
│   └── agent.py           # Evaluator main loop
├── planner/
│   ├── agent.py           # Planner main loop
│   ├── planning.py        # Milestone generation
│   └── monitor.py         # Milestone monitoring + learning notes
├── api/
│   └── main.py            # FastAPI central data API
├── dashboard/
│   └── index.html         # Web dashboard (vanilla JS)
├── deploy/
│   └── *.service          # systemd unit files
└── tests/                 # pytest test suite (117 tests)
```
