from dataclasses import replace
from datetime import date, datetime

from job_identifier.filter import collapse_recruiter_variants, _base_title
from job_identifier.models import Posting, RoleType, Seniority


def _posting(title: str, company: str = "Apex Systems", posted: date = date(2026, 5, 1), desc: str = "Foundry work.") -> Posting:
    return Posting(
        posting_id=f"id-{title}-{posted}",
        source="serpapi",
        source_url="https://x.com",
        fetched_at=datetime(2026, 5, 22),
        title=title,
        company=company,
        company_normalized=company.lower(),
        location="USA",
        country="US",
        posted_date=posted,
        description=desc,
        description_excerpt="",
        skill_matches=[],
        industry_match=False,
        role_type=RoleType.OTHER,
        seniority=Seniority.IC,
        recency_score=0.0,
        seniority_score=0.0,
        score=0.0,
        is_new=False,
    )


def test_base_title_strips_trailing_digits_only():
    assert _base_title("Palantir Platform Engineer 14") == "Palantir Platform Engineer"
    assert _base_title("Foundry Data Engineer & Architect 1") == "Foundry Data Engineer & Architect"
    assert _base_title("Sr Engineer #42") == "Sr Engineer"
    # Should NOT strip roman numerals or "L4"-style level codes
    assert _base_title("Engineer II") == "Engineer II"
    assert _base_title("Sr Engineer L4") == "Sr Engineer L4"
    # Should NOT touch titles without trailing numbers
    assert _base_title("Senior Palantir Engineer") == "Senior Palantir Engineer"


def test_collapse_groups_numbered_variants_to_one():
    postings = [
        _posting("Palantir Platform Engineer 14"),
        _posting("Palantir Platform Engineer 17"),
        _posting("Palantir Platform Engineer 32"),
    ]
    out = collapse_recruiter_variants(postings)
    assert len(out) == 1


def test_collapse_picks_most_recent_representative():
    older = _posting("Palantir Engineer 1", posted=date(2026, 4, 1), desc="short")
    newer = _posting("Palantir Engineer 2", posted=date(2026, 5, 15), desc="much longer body")
    out = collapse_recruiter_variants([older, newer])
    assert len(out) == 1
    assert out[0].posted_date == date(2026, 5, 15)


def test_collapse_preserves_unique_titles():
    a = _posting("Palantir Engineer")
    b = _posting("Palantir Architect")
    out = collapse_recruiter_variants([a, b])
    assert len(out) == 2


def test_collapse_respects_company_boundary():
    # Same base title at two different companies — keep both
    apex = _posting("Engineer 1", company="Apex Systems")
    sysone = _posting("Engineer 5", company="System One")
    out = collapse_recruiter_variants([apex, sysone])
    assert len(out) == 2


def test_collapse_does_not_merge_distinct_roles_with_same_company():
    p1 = _posting("Palantir Engineer", company="Acme")
    p2 = _posting("Palantir Architect", company="Acme")
    out = collapse_recruiter_variants([p1, p2])
    assert len(out) == 2
