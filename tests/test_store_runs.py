from datetime import datetime
from job_identifier.store import Store


def test_record_run_creates_row():
    store = Store(":memory:")
    store.init_schema()
    store.record_run(
        run_id="run_abc",
        run_name="palantir_insurance",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok",
        config_snapshot={"name": "palantir_insurance"},
        summary={"postings": 12, "new": 4},
        error=None,
    )
    rows = list(store.db["runs"].rows)
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert "palantir_insurance" in rows[0]["config_snapshot"]


def test_link_posting_to_run():
    store = Store(":memory:")
    store.init_schema()
    store.link_posting_to_run(
        run_id="run_abc", posting_id="p1", is_new=True, score=0.75
    )
    rows = list(store.db["posting_run_link"].rows)
    assert len(rows) == 1
    assert rows[0]["is_new"] == 1
    assert rows[0]["score"] == 0.75


def test_last_run_for_name_returns_most_recent():
    store = Store(":memory:")
    store.init_schema()
    store.record_run(
        run_id="r1", run_name="x",
        started_at=datetime(2026, 5, 13, 8, 0),
        finished_at=datetime(2026, 5, 13, 8, 5),
        status="ok", config_snapshot={}, summary={}, error=None,
    )
    store.record_run(
        run_id="r2", run_name="x",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok", config_snapshot={}, summary={}, error=None,
    )
    assert store.last_run_for_name("x")["run_id"] == "r2"


def test_last_run_for_unknown_name_returns_none():
    store = Store(":memory:")
    store.init_schema()
    assert store.last_run_for_name("unknown") is None
