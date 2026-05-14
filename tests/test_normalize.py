from datetime import date
from job_identifier.normalize import normalize_serpapi_jobs


def test_normalize_produces_expected_count(raw_serpapi_response, fixed_now):
    postings = normalize_serpapi_jobs(raw_serpapi_response, fetched_at=fixed_now)
    assert len(postings) == 4


def test_normalize_first_posting_fields(raw_serpapi_response, fixed_now):
    postings = normalize_serpapi_jobs(raw_serpapi_response, fetched_at=fixed_now)
    p = postings[0]
    assert p.title == "Senior Palantir Foundry Engineer"
    assert p.company == "Acme Insurance Inc"
    assert p.company_normalized == "acme insurance"
    assert p.location == "New York, NY"
    assert p.country == "US"
    assert p.posted_date == date(2026, 5, 8)
    assert p.source == "serpapi"
    assert p.source_url == "https://linkedin.com/jobs/view/1234"
    assert p.fetched_at == fixed_now


def test_normalize_bermuda_posting(raw_serpapi_response, fixed_now):
    postings = normalize_serpapi_jobs(raw_serpapi_response, fetched_at=fixed_now)
    bm = next(p for p in postings if p.country == "BM")
    assert bm.company_normalized == "hamilton re"
    assert bm.posted_date == date(2026, 5, 1)


def test_posting_id_is_stable(raw_serpapi_response, fixed_now):
    a = normalize_serpapi_jobs(raw_serpapi_response, fetched_at=fixed_now)
    b = normalize_serpapi_jobs(raw_serpapi_response, fetched_at=fixed_now)
    assert [p.posting_id for p in a] == [p.posting_id for p in b]


def test_classification_fields_are_unfilled(raw_serpapi_response, fixed_now):
    """normalize does NOT classify — that's filter's job."""
    postings = normalize_serpapi_jobs(raw_serpapi_response, fetched_at=fixed_now)
    for p in postings:
        assert p.skill_matches == []
        assert p.industry_match is False
        assert p.score == 0.0
