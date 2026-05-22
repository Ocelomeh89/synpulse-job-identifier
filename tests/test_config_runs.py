from pathlib import Path
from job_identifier.config import load_runs


def test_load_palantir_insurance_run():
    runs = load_runs(Path("config/runs.yaml"))
    assert len(runs) == 1
    r = runs[0]
    assert r.name == "palantir_insurance"
    assert r.enabled is True
    assert r.skill.hard_match_regex == r"\b(Foundry|AIP|Apollo)\b"
    assert "insurance" in r.industry.include_keywords
    assert "seguros" in r.industry.include_keywords
    assert "broker" in r.industry.include_keywords
    assert "Palantir Technologies" in r.industry.deny_companies
    assert "Acrisure" in r.industry.allow_companies
    assert r.geos == ["US", "CA", "MX", "UK", "BM"]
    assert r.recency_window_days == 90
    assert r.score_weights.recency == 0.6
    assert r.score_weights.seniority == 0.4
    assert r.enrichment.firecrawl_min_jd_chars == 500
    assert r.output.companies_tab == "Companies"
