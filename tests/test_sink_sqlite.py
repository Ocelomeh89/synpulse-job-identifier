from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority, RunResult
from job_identifier.sink.sqlite import write_run
from job_identifier.store import Store


def _p(pid: str, is_new: bool = True, score: float = 0.5) -> Posting:
    return Posting(
        posting_id=pid,
        source="s", source_url="u", fetched_at=datetime(2026, 5, 13),
        title="t", company="c", company_normalized="c",
        location="l", country="US", posted_date=date(2026, 5, 1),
        description="d", description_excerpt="",
        skill_matches=[], industry_match=False,
        role_type=RoleType.OTHER, seniority=Seniority.IC,
        recency_score=0.0, seniority_score=0.0, score=score,
        is_new=is_new,
    )


def test_write_run_persists_postings_and_links():
    store = Store(":memory:")
    store.init_schema()
    result = RunResult(
        run_id="r1", run_name="x",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok", summary={"total": 2},
    )
    write_run(store, [_p("a"), _p("b", is_new=False, score=0.7)], result, config_snapshot={})
    assert len(list(store.db["postings"].rows)) == 2
    assert len(list(store.db["posting_run_link"].rows)) == 2
    assert store.last_run_for_name("x")["run_id"] == "r1"


def test_write_run_is_idempotent_on_replay():
    store = Store(":memory:")
    store.init_schema()
    result = RunResult(
        run_id="r1", run_name="x",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok",
    )
    write_run(store, [_p("a")], result, config_snapshot={})
    write_run(store, [_p("a")], result, config_snapshot={})
    assert len(list(store.db["posting_run_link"].rows)) == 1
