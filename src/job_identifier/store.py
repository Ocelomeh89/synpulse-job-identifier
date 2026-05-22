from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from sqlite_utils import Database

from job_identifier.models import Posting


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


def writable_dir_for(preferred_dir: Path) -> Path:
    """Return preferred_dir if writable, else a /tmp fallback mirroring its name.

    Streamlit Cloud mounts the repo read-only at /mount/src, so relative paths
    like `data/...` can't be created there. /tmp is always writable but
    ephemeral — fine because dedupe state and per-run logs are already
    documented as ephemeral on Cloud.
    """
    try:
        preferred_dir.mkdir(parents=True, exist_ok=True)
        probe = preferred_dir / ".write_probe"
        probe.touch()
        probe.unlink()
        return preferred_dir
    except OSError:
        fallback = Path("/tmp/job_identifier") / preferred_dir.name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class Store:
    def __init__(self, path: str | Path):
        path = Path(path)
        if str(path) == ":memory:":
            self.db = Database(":memory:")
            return
        writable_dir = writable_dir_for(path.parent)
        self.db = Database(writable_dir / path.name)

    def init_schema(self) -> None:
        self.db.executescript(_SCHEMA_SQL)


def upsert_posting(self, posting: Posting, seen_at: datetime) -> bool:
    """Returns True if newly inserted, False if already existed."""
    ts = seen_at.isoformat()
    try:
        existing = self.db["postings"].get(posting.posting_id)
    except Exception:
        existing = None
    if existing is None:
        self.db["postings"].insert({
            "posting_id": posting.posting_id,
            "payload": json.dumps(posting.to_dict()),
            "first_seen_at": ts,
            "last_seen_at": ts,
        }, pk="posting_id")
        return True
    self.db["postings"].update(posting.posting_id, {
        "payload": json.dumps(posting.to_dict()),
        "last_seen_at": ts,
    })
    return False


def posting_exists(self, posting_id: str) -> bool:
    try:
        self.db["postings"].get(posting_id)
        return True
    except Exception:
        return False


def record_run(
    self,
    run_id: str,
    run_name: str,
    started_at: datetime,
    finished_at: datetime | None,
    status: str,
    config_snapshot: dict,
    summary: dict,
    error: str | None,
) -> None:
    self.db["runs"].insert({
        "run_id": run_id,
        "run_name": run_name,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat() if finished_at else None,
        "status": status,
        "config_snapshot": json.dumps(config_snapshot),
        "summary": json.dumps(summary),
        "error": error,
    }, pk="run_id", replace=True)


def link_posting_to_run(self, run_id: str, posting_id: str, is_new: bool, score: float) -> None:
    self.db["posting_run_link"].insert({
        "run_id": run_id,
        "posting_id": posting_id,
        "is_new": 1 if is_new else 0,
        "score": score,
    }, pk=("run_id", "posting_id"), replace=True)


def last_run_for_name(self, run_name: str) -> dict | None:
    rows = list(self.db.query(
        "SELECT * FROM runs WHERE run_name = ? ORDER BY started_at DESC LIMIT 1",
        [run_name],
    ))
    return rows[0] if rows else None


Store.upsert_posting = upsert_posting
Store.posting_exists = posting_exists
Store.record_run = record_run
Store.link_posting_to_run = link_posting_to_run
Store.last_run_for_name = last_run_for_name
