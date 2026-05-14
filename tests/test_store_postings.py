from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.store import Store


def _posting() -> Posting:
    return Posting(
        posting_id="abc",
        source="serpapi",
        source_url="https://x.com",
        fetched_at=datetime(2026, 5, 13, 10, 0, 0),
        title="Engineer",
        company="Acme",
        company_normalized="acme",
        location="NYC",
        country="US",
        posted_date=date(2026, 5, 1),
        description="d",
        description_excerpt="",
        skill_matches=["Foundry"],
        industry_match=True,
        role_type=RoleType.ENGINEERING,
        seniority=Seniority.IC,
        recency_score=0.5,
        seniority_score=0.2,
        score=0.38,
        is_new=False,
    )


def test_upsert_new_posting_marks_is_new():
    store = Store(":memory:")
    store.init_schema()
    p = _posting()
    is_new = store.upsert_posting(p, seen_at=datetime(2026, 5, 13, 10, 0, 0))
    assert is_new is True
    rows = list(store.db["postings"].rows)
    assert len(rows) == 1
    assert rows[0]["posting_id"] == "abc"


def test_upsert_existing_posting_returns_false():
    store = Store(":memory:")
    store.init_schema()
    p = _posting()
    store.upsert_posting(p, seen_at=datetime(2026, 5, 13))
    is_new = store.upsert_posting(p, seen_at=datetime(2026, 5, 14))
    assert is_new is False
    rows = list(store.db["postings"].rows)
    assert len(rows) == 1
    assert rows[0]["last_seen_at"].startswith("2026-05-14")


def test_lookup_posting_returns_payload():
    store = Store(":memory:")
    store.init_schema()
    p = _posting()
    store.upsert_posting(p, seen_at=datetime(2026, 5, 13))
    assert store.posting_exists("abc") is True
    assert store.posting_exists("xyz") is False
