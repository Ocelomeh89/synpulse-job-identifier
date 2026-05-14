from dataclasses import replace
from datetime import date, datetime
import pytest
from job_identifier.score import (
    recency_score, seniority_score, combined, apply as score_apply,
)
from job_identifier.models import (
    EnrichmentConfig, OutputConfig, Posting, RoleType, RunConfig,
    RunIndustryConfig, RunSkillConfig, ScoreWeights, Seniority,
)


def test_recency_score_fresh_posting():
    posted = date(2026, 5, 12)
    now = datetime(2026, 5, 13)
    assert recency_score(posted, now, window_days=90) == pytest.approx(89.0 / 90.0)


def test_recency_score_at_window_edge():
    posted = date(2026, 2, 12)  # 90 days before 2026-05-13
    now = datetime(2026, 5, 13)
    assert recency_score(posted, now, window_days=90) == pytest.approx(0.0)


def test_recency_score_outside_window_clamped_to_zero():
    posted = date(2025, 1, 1)
    now = datetime(2026, 5, 13)
    assert recency_score(posted, now, window_days=90) == 0.0


def test_seniority_score_table():
    assert seniority_score(Seniority.IC) == 0.20
    assert seniority_score(Seniority.SENIOR_IC) == 0.40
    assert seniority_score(Seniority.LEAD) == 0.60
    assert seniority_score(Seniority.DIRECTOR) == 0.85
    assert seniority_score(Seniority.VP_PLUS) == 1.00


def test_combined():
    weights = ScoreWeights(recency=0.6, seniority=0.4)
    assert combined(1.0, 1.0, weights) == pytest.approx(1.0)
    assert combined(0.5, 0.5, weights) == pytest.approx(0.5)
    assert combined(1.0, 0.0, weights) == pytest.approx(0.6)


def test_apply_writes_scores_to_postings():
    cfg = RunConfig(
        name="x", enabled=True,
        skill=RunSkillConfig(hard_match_regex="x", query_terms=[]),
        industry=RunIndustryConfig(include_keywords=[], deny_companies=[]),
        geos=[], recency_window_days=90,
        score_weights=ScoreWeights(recency=0.6, seniority=0.4),
        enrichment=EnrichmentConfig(firecrawl_min_jd_chars=500),
        output=OutputConfig(companies_tab="C", postings_tab="P", archived_tab="A"),
    )
    p = Posting(
        posting_id="x", source="s", source_url="u",
        fetched_at=datetime(2026, 5, 13),
        title="t", company="c", company_normalized="c",
        location="l", country="US", posted_date=date(2026, 5, 12),
        description="d", description_excerpt="",
        skill_matches=["Foundry"], industry_match=True,
        role_type=RoleType.ENGINEERING, seniority=Seniority.VP_PLUS,
        recency_score=0.0, seniority_score=0.0, score=0.0, is_new=False,
    )
    [scored] = score_apply([p], cfg, now=datetime(2026, 5, 13))
    assert scored.recency_score == pytest.approx(89.0 / 90.0)
    assert scored.seniority_score == 1.0
    assert scored.score == pytest.approx(0.6 * (89.0 / 90.0) + 0.4 * 1.0)
