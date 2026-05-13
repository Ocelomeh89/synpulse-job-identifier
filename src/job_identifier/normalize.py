from __future__ import annotations
import hashlib
import re
from datetime import date, datetime, timedelta

from job_identifier.country import country_from_location
from job_identifier.models import Posting, RoleType, Seniority

_SUFFIX_PATTERN = re.compile(
    r"\b(inc|incorporated|ltd|limited|llc|llp|plc|corp|corporation|company|co|"
    r"s\.?a\.?|s\.?a\.?s\.?|ag|gmbh|holdings|group)\b\.?",
    re.IGNORECASE,
)
_PUNCT_PATTERN = re.compile(r"[^\w\s]")
_WS_PATTERN = re.compile(r"\s+")


def normalize_company(name: str) -> str:
    s = name.lower()
    s = _SUFFIX_PATTERN.sub(" ", s)
    s = _PUNCT_PATTERN.sub(" ", s)
    s = _WS_PATTERN.sub(" ", s).strip()
    return s


_RELATIVE_DATE_PATTERN = re.compile(
    r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago",
    re.IGNORECASE,
)


def parse_posted_at(posted_at: str, fetched_at: datetime) -> date | None:
    m = _RELATIVE_DATE_PATTERN.search(posted_at or "")
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    delta_days = {
        "minute": 0,
        "hour": 0,
        "day": n,
        "week": 7 * n,
        "month": 30 * n,
    }[unit]
    return (fetched_at - timedelta(days=delta_days)).date()


def posting_id_for(company_normalized: str, title: str, country: str, posted_date: date) -> str:
    key = f"{company_normalized}|{title.lower()}|{country}|{posted_date.isoformat()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _extract_url(job: dict) -> str:
    opts = job.get("apply_options") or []
    if opts and isinstance(opts, list):
        link = opts[0].get("link")
        if link:
            return link
    return job.get("share_link", "")


def normalize_serpapi_jobs(response: dict, fetched_at: datetime) -> list[Posting]:
    jobs = response.get("jobs_results", [])
    out: list[Posting] = []
    for job in jobs:
        company = job.get("company_name") or ""
        title = job.get("title") or ""
        location = job.get("location") or ""
        description = job.get("description") or ""
        posted_at_text = (job.get("detected_extensions") or {}).get("posted_at", "")
        posted_date = parse_posted_at(posted_at_text, fetched_at)
        if not (company and title and description and posted_date):
            continue
        country = country_from_location(location)
        company_normalized = normalize_company(company)
        out.append(
            Posting(
                posting_id=posting_id_for(company_normalized, title, country, posted_date),
                source="serpapi",
                source_url=_extract_url(job),
                fetched_at=fetched_at,
                title=title,
                company=company,
                company_normalized=company_normalized,
                location=location,
                country=country,
                posted_date=posted_date,
                description=description,
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
        )
    return out
