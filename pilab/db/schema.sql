-- PiLab schema v1
-- All IDs are ULIDs (TEXT).  All timestamps are UTC ISO 8601 TEXT.

PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);

-- -----------------------------------------------------------------------
-- Core tables
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS findings (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    summary         TEXT,
    source_type     TEXT NOT NULL,
    source_url      TEXT,
    topic_tags      TEXT,            -- comma-separated
    raw_content     TEXT,
    scout_pi        TEXT,
    status          TEXT NOT NULL DEFAULT 'scouted',
    discovered_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS evaluations (
    id                      TEXT PRIMARY KEY,
    finding_id              TEXT NOT NULL REFERENCES findings(id),
    novelty_score           INTEGER,
    pi_feasibility_score    INTEGER,
    feasibility_notes       TEXT,
    ram_estimate_gb         REAL,
    requires_gpu            INTEGER DEFAULT 0,   -- 0/1 boolean
    verdict                 TEXT,                 -- approved | rejected
    verdict_reason          TEXT,
    evaluated_by            TEXT,
    evaluated_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,
    finding_id      TEXT NOT NULL REFERENCES findings(id),
    evaluation_id   TEXT REFERENCES evaluations(id),
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'awaiting_approval',
    topic_tags      TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    started_at      TEXT,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS milestones (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    sequence        INTEGER NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    done_condition  TEXT,
    category        TEXT,
    estimated_days  INTEGER,
    status          TEXT NOT NULL DEFAULT 'pending',
    due_date        TEXT,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS learnings (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    milestone_id    TEXT REFERENCES milestones(id),
    category        TEXT,
    note            TEXT NOT NULL,
    agent           TEXT,
    logged_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS rejections (
    id              TEXT PRIMARY KEY,
    finding_id      TEXT NOT NULL REFERENCES findings(id),
    evaluation_id   TEXT REFERENCES evaluations(id),
    reason_code     TEXT,
    reason_detail   TEXT,
    rejected_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS agent_events (
    id              TEXT PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    entity_id       TEXT,
    message         TEXT,
    occurred_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS seen_urls (
    hash        TEXT PRIMARY KEY,
    seen_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS job_queue (
    id          TEXT PRIMARY KEY,
    finding_id  TEXT NOT NULL REFERENCES findings(id),
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | claimed | done | error
    error_message TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    claimed_at  TEXT,
    claimed_by  TEXT
);

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_discovered ON findings(discovered_at);
CREATE INDEX IF NOT EXISTS idx_evaluations_finding ON evaluations(finding_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_finding ON projects(finding_id);
CREATE INDEX IF NOT EXISTS idx_milestones_project ON milestones(project_id);
CREATE INDEX IF NOT EXISTS idx_learnings_project ON learnings(project_id);
CREATE INDEX IF NOT EXISTS idx_learnings_milestone ON learnings(milestone_id);
CREATE INDEX IF NOT EXISTS idx_rejections_finding ON rejections(finding_id);
CREATE INDEX IF NOT EXISTS idx_agent_events_occurred ON agent_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_job_queue_status ON job_queue(status);
