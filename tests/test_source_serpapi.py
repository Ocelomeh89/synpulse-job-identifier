from unittest.mock import MagicMock

import pytest
from job_identifier.sources.serpapi_jobs import fetch_jobs
from job_identifier.models import (
    EnrichmentConfig, OutputConfig, RunConfig, RunIndustryConfig,
    RunSkillConfig, ScoreWeights,
)


@pytest.fixture
def run_config():
    return RunConfig(
        name="palantir_insurance",
        enabled=True,
        skill=RunSkillConfig(
            hard_match_regex=r"\b(Foundry|AIP)\b",
            query_terms=['"Palantir Foundry" insurance'],
        ),
        industry=RunIndustryConfig(include_keywords=["insurance"], deny_companies=[]),
        geos=["US"],
        recency_window_days=90,
        score_weights=ScoreWeights(recency=0.6, seniority=0.4),
        enrichment=EnrichmentConfig(firecrawl_min_jd_chars=500),
        output=OutputConfig(
            companies_tab="Companies", postings_tab="Postings", archived_tab="Archived"
        ),
    )


def test_fetch_jobs_calls_serpapi_per_geo_and_query(run_config, monkeypatch):
    mock_search = MagicMock()
    mock_search.return_value.get_dict.return_value = {"jobs_results": []}
    monkeypatch.setattr(
        "job_identifier.sources.serpapi_jobs.GoogleSearch", mock_search
    )
    fetch_jobs(run_config, api_key="sk_test")
    assert mock_search.call_count == 1  # 1 geo × 1 query
    params = mock_search.call_args.args[0]
    assert params["engine"] == "google_jobs"
    assert params["q"] == '"Palantir Foundry" insurance'
    assert params["api_key"] == "sk_test"


def test_fetch_jobs_aggregates_results_across_geos(run_config, monkeypatch):
    run_config = RunConfig(
        **{**run_config.__dict__, "geos": ["US", "CA"]}
    )
    mock_search = MagicMock()
    mock_search.return_value.get_dict.return_value = {
        "jobs_results": [{"title": "X", "company_name": "Y"}]
    }
    monkeypatch.setattr(
        "job_identifier.sources.serpapi_jobs.GoogleSearch", mock_search
    )
    results = fetch_jobs(run_config, api_key="sk_test")
    assert mock_search.call_count == 2  # 2 geos × 1 query
    assert len(results) == 2


def test_fetch_jobs_combines_response_dicts(run_config, monkeypatch):
    """Returns the same shape as a single SerpAPI response (jobs_results list)."""
    mock_search = MagicMock()
    mock_search.return_value.get_dict.return_value = {
        "jobs_results": [
            {"title": "A", "company_name": "Acme"},
            {"title": "B", "company_name": "Beta"},
        ]
    }
    monkeypatch.setattr(
        "job_identifier.sources.serpapi_jobs.GoogleSearch", mock_search
    )
    results = fetch_jobs(run_config, api_key="sk_test")
    assert len(results) == 1
    assert "jobs_results" in results[0]
    assert len(results[0]["jobs_results"]) == 2
