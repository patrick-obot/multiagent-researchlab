# PiLab — Multi-Agent Research Pipeline

A distributed research pipeline running across 3 Raspberry Pi 5 devices, using local LLMs via llama.cpp to scout, evaluate, plan, and track AI/Telco/Fintech/Edge research.

## Architecture

```
mypi (1TB NVMe)          pi2 (256GB SSD)         pi3 (256GB SSD)
+-----------------+      +-----------------+      +-----------------+
| SQLite DB       |      | Scout Agent     |      | Planner Agent   |
| FastAPI (8000)  |<---->| Phi-3 Mini(8080)|<---->| Phi-3 Mini(8082)|
| Evaluator Agent |      |                 |      |                 |
| Qwen 7B (8081)  |      +-----------------+      +-----------------+
+-----------------+
        ^                         ^                         ^
        |         Gigabit Ethernet (HTTP API)                |
        +------------------------+---------------------------+
```

All inter-agent communication goes through the central FastAPI on mypi (no NFS/shared filesystem).

## Pipeline Flow

1. **Scout** (pi2) polls sources (HN, GitHub, arXiv, Reddit, RSS, YouTube) on configurable intervals
2. Findings are filtered by topic keywords (AI, Telco, Fintech, Edge) and summarised by Phi-3 Mini
3. **Evaluator** (mypi) claims jobs from the queue, scores novelty + Pi feasibility via Qwen 7B
4. Approved findings become projects; rejected ones are archived with reason codes
5. **Planner** (pi3) generates milestones for approved projects via Phi-3 Mini
6. Dashboard shows the full pipeline state with live agent status

## Setup

### Prerequisites (all Pis)

```bash
# Install Python deps
cd /home/mypi/Projects/multiagent_researchlab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### mypi — Database, API, Evaluator

```bash
# Create DB directory
sudo mkdir -p /mnt/pilab
sudo chown mypi:mypi /mnt/pilab

# Download Qwen2.5 7B Q4
# Place GGUF at a known path, e.g. /mnt/pilab/models/qwen2.5-7b-q4_k_m.gguf

# Start llama.cpp server
llama-server -m /mnt/pilab/models/qwen2.5-7b-q4_k_m.gguf \
  --host 0.0.0.0 --port 8081 -c 2048 -ngl 0

# Install and start services
sudo cp pilab/deploy/pilab-api.service /etc/systemd/system/
sudo cp pilab/deploy/pilab-evaluator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pilab-api pilab-evaluator
```

### pi2 — Scout

```bash
# Download Phi-3 Mini Q4
# Place GGUF at a known path

# Start llama.cpp server
llama-server -m /path/to/phi-3-mini-q4_k_m.gguf \
  --host 0.0.0.0 --port 8080 -c 2048 -ngl 0

# Install and start service
sudo cp pilab/deploy/pilab-scout.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pilab-scout
```

### pi3 — Planner

```bash
# Download Phi-3 Mini Q4 (same model as pi2)

# Start llama.cpp server
llama-server -m /path/to/phi-3-mini-q4_k_m.gguf \
  --host 0.0.0.0 --port 8082 -c 2048 -ngl 0

# Install and start service
sudo cp pilab/deploy/pilab-planner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pilab-planner
```

### Dashboard

The dashboard is served from the FastAPI app at `http://mypi:8000/dashboard/`.
No separate server needed.

## Configuration

All settings can be overridden via environment variables prefixed with `PILAB_`.
See `pilab/config.py` for the full list. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PILAB_DB_PATH` | `/mnt/pilab/pilab.db` | SQLite database path |
| `PILAB_API_BASE_URL` | `http://mypi:8000` | Central API URL |
| `PILAB_LLM_SCOUT_URL` | `http://localhost:8080` | Scout LLM endpoint |
| `PILAB_LLM_EVALUATOR_URL` | `http://localhost:8081` | Evaluator LLM endpoint |
| `PILAB_LLM_PLANNER_URL` | `http://localhost:8082` | Planner LLM endpoint |
| `PILAB_LOG_LEVEL` | `INFO` | Logging level |

## Testing

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

116 tests covering all modules:
- DB store (34), migrations (4), shared modules (21)
- Scout filter/dedup/summariser/sources (20)
- Evaluator verdict logic (5), Planner milestones/monitor (5)
- API endpoints (23)

All tests use in-memory SQLite and mocked LLM/HTTP calls — no external services required.

## Monitoring

- Dashboard: `http://mypi:8000/dashboard/`
- Swagger docs: `http://mypi:8000/docs`
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
│   ├── llm.py             # llama.cpp HTTP client with JSON repair
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
│   └── *.service           # systemd unit files
└── tests/                  # pytest test suite (116 tests)
```
