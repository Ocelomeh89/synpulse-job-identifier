from datetime import date, datetime
from unittest.mock import MagicMock

from job_identifier.enrich.firecrawl_jd import fill_short_descriptions
from job_identifier.models import Posting, RoleType, Seniority


def _p(desc: str, url: str = "https://x.com") -> Posting:
    return Posting(
        posting_id="p", source="s", source_url=url, fetched_at=datetime(2026, 5, 13),
        title="t", company="c", company_normalized="c", location="l", country="US",
        posted_date=date(2026, 5, 1),
        description=desc, description_excerpt="",
        skill_matches=[], industry_match=False,
        role_type=RoleType.OTHER, seniority=Seniority.IC,
        recency_score=0.0, seniority_score=0.0, score=0.0, is_new=False,
    )


def test_skips_long_descriptions(monkeypatch):
    long_desc = "X" * 600
    client = MagicMock()
    out = fill_short_descriptions([_p(long_desc)], min_chars=500, client=client)
    assert client.scrape_url.call_count == 0
    assert out[0].description == long_desc


def test_replaces_short_description_when_firecrawl_returns_longer():
    client = MagicMock()
    client.scrape_url.return_value = {"markdown": "Y" * 1000}
    out = fill_short_descriptions([_p("short", url="https://job.example/1")], min_chars=500, client=client)
    assert len(out[0].description) == 1000
    client.scrape_url.assert_called_once_with("https://job.example/1")


def test_keeps_original_if_firecrawl_returns_shorter():
    client = MagicMock()
    client.scrape_url.return_value = {"markdown": "tiny"}
    out = fill_short_descriptions([_p("original short")], min_chars=500, client=client)
    assert out[0].description == "original short"


def test_keeps_original_on_firecrawl_exception():
    client = MagicMock()
    client.scrape_url.side_effect = RuntimeError("network down")
    out = fill_short_descriptions([_p("original short")], min_chars=500, client=client)
    assert out[0].description == "original short"
