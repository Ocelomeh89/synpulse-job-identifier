from __future__ import annotations
from pathlib import Path

from sqlite_utils import Database


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS postings (
  posting_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  run_name TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  config_snapshot TEXT NOT NULL,
  summary TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS posting_run_link (
  run_id TEXT NOT NULL,
  posting_id TEXT NOT NULL,
  is_new INTEGER NOT NULL,
  score REAL,
  PRIMARY KEY (run_id, posting_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_name_started ON runs(run_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_link_run ON posting_run_link(run_id);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = Database(path)

    def init_schema(self) -> None:
        self.db.executescript(_SCHEMA_SQL)
