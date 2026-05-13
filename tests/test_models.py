from datetime import date, datetime
from dataclasses import FrozenInstanceError
from job_identifier.models import Posting, RoleType, Seniority


def test_posting_is_frozen():
    p = _sample_posting()
    try:
        p.title = "Other"  # type: ignore[misc]
    except FrozenInstanceError:
        pass  # Expected - frozen dataclass cannot be modified
    except Exception as e:
        raise AssertionError(f"Expected FrozenInstanceError, got {type(e).__name__}: {e}")
    else:
        raise AssertionError("Posting should be immutable")


def test_posting_serializes_to_dict():
    p = _sample_posting()
    d = p.to_dict()
    assert d["title"] == "Senior Palantir Foundry Engineer"
    assert d["role_type"] == "ENGINEERING"
    assert d["seniority"] == "SENIOR_IC"
    assert d["posted_date"] == "2026-05-01"


def test_posting_roundtrips_through_dict():
    p = _sample_posting()
    d = p.to_dict()
    p2 = Posting.from_dict(d)
    assert p2 == p


def _sample_posting() -> Posting:
    return Posting(
        posting_id="abc123",
        source="serpapi",
        source_url="https://example.com/job/1",
        fetched_at=datetime(2026, 5, 13, 10, 0, 0),
        title="Senior Palantir Foundry Engineer",
        company="Acme Insurance Inc",
        company_normalized="acme insurance",
        location="New York, NY",
        country="US",
        posted_date=date(2026, 5, 1),
        description="We're hiring a Palantir Foundry engineer...",
        description_excerpt="...Palantir Foundry engineer...",
        skill_matches=["Foundry"],
        industry_match=True,
        role_type=RoleType.ENGINEERING,
        seniority=Seniority.SENIOR_IC,
        recency_score=0.87,
        seniority_score=0.40,
        score=0.69,
        is_new=True,
    )
