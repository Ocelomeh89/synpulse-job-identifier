from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
from job_identifier.filter import apply as filter_apply
from job_identifier.models import (
    EnrichmentConfig, OutputConfig, Posting, RoleType, RunConfig,
    RunIndustryConfig, RunSkillConfig, ScoreWeights, Seniority,
)


def _config():
    return RunConfig(
        name="palantir_insurance",
        enabled=True,
        skill=RunSkillConfig(
            hard_match_regex=r"\b(Foundry|AIP)\b",
            query_terms=[],
        ),
        industry=RunIndustryConfig(
            include_keywords=["insurance", "reinsurance"],
            deny_companies=["Accenture", "Palantir Technologies"],
        ),
        geos=["US"],
        recency_window_days=90,
        score_weights=ScoreWeights(recency=0.6, seniority=0.4),
        enrichment=EnrichmentConfig(firecrawl_min_jd_chars=500),
        output=OutputConfig(
            companies_tab="Companies", postings_tab="Postings", archived_tab="Archived"
        ),
    )


def _posting(**overrides) -> Posting:
    base = Posting(
        posting_id="p1",
        source="serpapi",
        source_url="https://x.com",
        fetched_at=datetime(2026, 5, 13),
        title="Senior Palantir Foundry Engineer",
        company="Acme Insurance",
        company_normalized="acme insurance",
        location="New York, NY",
        country="US",
        posted_date=date(2026, 5, 1),
        description="We need a Foundry engineer for our insurance platform.",
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
    for k, v in overrides.items():
        base = replace(base, **{k: v})
    return base


def test_drops_no_skill_match():
    posting = _posting(description="Marketing role, no tech.")
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_drops_no_industry_match():
    posting = _posting(
        title="Foundry Engineer",
        description="We build Foundry for healthcare.",
        company="Health Co",
        company_normalized="health co",
    )
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_drops_too_old():
    posting = _posting(posted_date=date(2026, 1, 1))  # >90 days from 2026-05-13
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_drops_denied_company():
    posting = _posting(
        company="Accenture",
        company_normalized="accenture",
        description="Foundry consulting for insurance clients.",
    )
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_keeps_valid_posting_with_classification():
    posting = _posting()
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert len(out) == 1
    p = out[0]
    assert p.skill_matches == ["Foundry"]
    assert p.industry_match is True
    assert p.role_type == RoleType.ENGINEERING
    assert p.seniority == Seniority.SENIOR_IC
    assert p.description_excerpt != ""
