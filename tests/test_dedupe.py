from datetime import date, datetime
from job_identifier.dedupe import tag_is_new
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.store import Store


def _p(pid: str) -> Posting:
    return Posting(
        posting_id=pid,
        source="s", source_url="u", fetched_at=datetime(2026, 5, 13),
        title="t", company="c", company_normalized="c",
        location="l", country="US", posted_date=date(2026, 5, 1),
        description="d", description_excerpt="",
        skill_matches=[], industry_match=False,
        role_type=RoleType.OTHER, seniority=Seniority.IC,
        recency_score=0.0, seniority_score=0.0, score=0.0, is_new=False,
    )


def test_all_new_when_store_empty():
    store = Store(":memory:")
    store.init_schema()
    tagged = tag_is_new([_p("a"), _p("b")], store)
    assert all(p.is_new for p in tagged)


def test_marks_existing_as_not_new():
    store = Store(":memory:")
    store.init_schema()
    store.upsert_posting(_p("a"), seen_at=datetime(2026, 5, 12))
    tagged = tag_is_new([_p("a"), _p("b")], store)
    by_id = {p.posting_id: p.is_new for p in tagged}
    assert by_id["a"] is False
    assert by_id["b"] is True
