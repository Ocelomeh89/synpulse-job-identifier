from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.sink.sheets import build_postings_rows, merge_preserved_edits


def _p(pid: str, score: float = 0.5) -> Posting:
    return Posting(
        posting_id=pid, source="s", source_url=f"https://x.com/{pid}",
        fetched_at=datetime(2026, 5, 13),
        title="Senior Foundry Engineer", company="Acme", company_normalized="acme",
        location="NYC", country="US", posted_date=date(2026, 5, 10),
        description="d", description_excerpt="...Foundry...",
        skill_matches=["Foundry"], industry_match=True,
        role_type=RoleType.ENGINEERING, seniority=Seniority.SENIOR_IC,
        recency_score=0.96, seniority_score=0.40, score=score, is_new=True,
    )


def test_build_postings_rows_sorted_by_score():
    rows = build_postings_rows([_p("a", 0.3), _p("b", 0.9)])
    assert rows[0]["posting_id"] == "b"
    assert rows[1]["posting_id"] == "a"
    assert rows[0]["is_new"] == "NEW"


def test_merge_preserved_edits_keys_by_posting_id():
    new = [{"posting_id": "a", "assigned_to": "", "notes": "", "company": "X", "title": "T"}]
    existing = [{"posting_id": "a", "assigned_to": "alice", "notes": "follow up"}]
    merged, archived = merge_preserved_edits(
        new_rows=new, existing_rows=existing, key_field="posting_id"
    )
    assert merged[0]["assigned_to"] == "alice"
    assert merged[0]["notes"] == "follow up"
    assert archived == []


def test_merge_archives_lost_edits():
    new: list[dict] = []
    existing = [{"posting_id": "gone", "assigned_to": "alice", "notes": "n"}]
    merged, archived = merge_preserved_edits(
        new_rows=new, existing_rows=existing, key_field="posting_id"
    )
    assert len(archived) == 1
    assert archived[0]["posting_id"] == "gone"


def test_merge_does_not_archive_empty_existing():
    new: list[dict] = []
    existing = [{"posting_id": "gone", "assigned_to": "", "notes": ""}]
    merged, archived = merge_preserved_edits(
        new_rows=new, existing_rows=existing, key_field="posting_id"
    )
    assert archived == []
