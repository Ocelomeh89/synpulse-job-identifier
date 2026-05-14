from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.sink.sheets import aggregate_companies


def _p(company: str, score: float, seniority: Seniority, role_type: RoleType,
       skill_matches: list[str], country: str, posted: date,
       url: str = "https://x.com") -> Posting:
    return Posting(
        posting_id=f"{company}-{posted}",
        source="s", source_url=url, fetched_at=datetime(2026, 5, 13),
        title="t", company=company, company_normalized=company.lower(),
        location="l", country=country, posted_date=posted,
        description="d", description_excerpt="",
        skill_matches=skill_matches, industry_match=True,
        role_type=role_type, seniority=seniority,
        recency_score=0.0, seniority_score=0.0, score=score, is_new=False,
    )


def test_aggregate_groups_by_company_normalized():
    postings = [
        _p("Acme", 0.5, Seniority.IC, RoleType.ENGINEERING, ["Foundry"], "US", date(2026, 5, 1)),
        _p("Acme", 0.8, Seniority.DIRECTOR, RoleType.LEADERSHIP, ["AIP"], "US", date(2026, 5, 10)),
        _p("Beta", 0.6, Seniority.SENIOR_IC, RoleType.DATA_AI, ["Foundry"], "GB", date(2026, 5, 5)),
    ]
    rows = aggregate_companies(postings)
    assert len(rows) == 2
    acme = next(r for r in rows if r["company"] == "Acme")
    assert acme["score"] == 0.8
    assert acme["open_roles"] == 2
    assert acme["most_recent_posting"] == "2026-05-10"
    assert acme["most_senior_role"] == "DIRECTOR"
    assert set(acme["role_type_mix"].split(", ")) == {"ENGINEERING", "LEADERSHIP"}
    assert set(acme["skill_matches"].split(", ")) == {"Foundry", "AIP"}
    assert acme["country"] == "US"
    assert "Acme" in acme["linkedin_company_search"]
    assert acme["relationship_status"] == "new prospect"


def test_aggregate_sorts_by_score_desc():
    postings = [
        _p("Low", 0.3, Seniority.IC, RoleType.ENGINEERING, ["Foundry"], "US", date(2026, 5, 1)),
        _p("High", 0.9, Seniority.DIRECTOR, RoleType.LEADERSHIP, ["AIP"], "US", date(2026, 5, 10)),
    ]
    rows = aggregate_companies(postings)
    assert rows[0]["company"] == "High"
    assert rows[1]["company"] == "Low"


def test_aggregate_sample_jd_url_is_most_recent():
    def _p_custom(score, posted, url):
        return Posting(
            posting_id=f"id-{posted}", source="s", source_url=url,
            fetched_at=datetime(2026,5,13), title="t", company="Acme",
            company_normalized="acme", location="l", country="US",
            posted_date=posted, description="d", description_excerpt="",
            skill_matches=["Foundry"], industry_match=True,
            role_type=RoleType.ENGINEERING, seniority=Seniority.IC,
            recency_score=0.0, seniority_score=0.0, score=score, is_new=False,
        )
    postings = [
        _p_custom(score=0.9, posted=date(2026, 5, 1), url="https://OLD-but-high-score"),
        _p_custom(score=0.3, posted=date(2026, 5, 10), url="https://NEW-low-score"),
    ]
    [row] = aggregate_companies(postings)
    assert row["sample_jd_url"] == "https://NEW-low-score"
