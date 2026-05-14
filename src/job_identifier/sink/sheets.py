from __future__ import annotations
from collections import Counter, defaultdict
from urllib.parse import quote_plus

from job_identifier.models import Posting, Seniority


_SENIORITY_ORDER = [
    Seniority.IC, Seniority.SENIOR_IC, Seniority.LEAD,
    Seniority.DIRECTOR, Seniority.VP_PLUS,
]


def _linkedin_search(company: str) -> str:
    return f"https://linkedin.com/search/results/companies/?keywords={quote_plus(company)}"


def aggregate_companies(postings: list[Posting]) -> list[dict]:
    by_company: dict[str, list[Posting]] = defaultdict(list)
    for p in postings:
        by_company[p.company].append(p)

    rows: list[dict] = []
    for company, group in by_company.items():
        top = max(group, key=lambda p: p.score)
        seniorities = {p.seniority for p in group}
        most_senior = max(seniorities, key=_SENIORITY_ORDER.index)
        role_types = sorted({p.role_type.value for p in group})
        skills = sorted({s for p in group for s in p.skill_matches})
        countries = Counter(p.country for p in group)
        majority_country = countries.most_common(1)[0][0]
        rows.append({
            "company": company,
            "relationship_status": "new prospect",
            "score": top.score,
            "open_roles": len(group),
            "most_recent_posting": max(p.posted_date for p in group).isoformat(),
            "most_senior_role": most_senior.value,
            "role_type_mix": ", ".join(role_types),
            "skill_matches": ", ".join(skills),
            "country": majority_country,
            "linkedin_company_search": _linkedin_search(company),
            "sample_jd_url": top.source_url,
            "assigned_to": "",
            "notes": "",
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
