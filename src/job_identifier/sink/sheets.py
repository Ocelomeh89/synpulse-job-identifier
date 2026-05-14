from __future__ import annotations
from collections import Counter, defaultdict
from typing import Protocol
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
            "sample_jd_url": max(group, key=lambda p: p.posted_date).source_url,
            "assigned_to": "",
            "notes": "",
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def build_postings_rows(postings: list[Posting]) -> list[dict]:
    rows = []
    for p in sorted(postings, key=lambda p: p.score, reverse=True):
        rows.append({
            "posting_id": p.posting_id,
            "company": p.company,
            "title": p.title,
            "location": p.location,
            "country": p.country,
            "posted_date": p.posted_date.isoformat(),
            "role_type": p.role_type.value,
            "seniority": p.seniority.value,
            "skill_matches": ", ".join(p.skill_matches),
            "score": p.score,
            "recency_score": p.recency_score,
            "seniority_score": p.seniority_score,
            "description_excerpt": p.description_excerpt,
            "job_url": p.source_url,
            "is_new": "NEW" if p.is_new else "",
            "linkedin_company_search": _linkedin_search(p.company),
            "assigned_to": "",
            "notes": "",
        })
    return rows


def merge_preserved_edits(
    new_rows: list[dict],
    existing_rows: list[dict],
    key_field: str,
) -> tuple[list[dict], list[dict]]:
    """Merge assigned_to/notes from existing_rows into new_rows by key_field.
    Returns (merged_new_rows, archived_rows_with_lost_edits)."""
    existing_by_key: dict[str, dict] = {
        r[key_field]: r for r in existing_rows if r.get(key_field)
    }
    merged: list[dict] = []
    for r in new_rows:
        key = r.get(key_field)
        prev = existing_by_key.get(key)
        if prev:
            r = {**r, "assigned_to": prev.get("assigned_to", ""), "notes": prev.get("notes", "")}
        merged.append(r)

    new_keys = {r.get(key_field) for r in new_rows}
    archived = [
        r for r in existing_rows
        if r.get(key_field) not in new_keys
        and (r.get("assigned_to") or r.get("notes"))
    ]
    return merged, archived


class TabProtocol(Protocol):
    def read_rows(self) -> list[dict]: ...
    def clear(self) -> None: ...
    def write_rows(self, rows: list[dict]) -> None: ...
    def append_rows(self, rows: list[dict]) -> None: ...


class WorkbookProtocol(Protocol):
    @property
    def companies_tab(self) -> TabProtocol: ...
    @property
    def postings_tab(self) -> TabProtocol: ...
    @property
    def archived_tab(self) -> TabProtocol: ...


def write_sheets(workbook, postings: list[Posting], output_config) -> None:
    existing_companies = workbook.companies_tab.read_rows()
    existing_postings = workbook.postings_tab.read_rows()

    new_companies = aggregate_companies(postings)
    new_postings = build_postings_rows(postings)

    merged_companies, archived_companies = merge_preserved_edits(
        new_companies, existing_companies, key_field="company",
    )
    merged_postings, archived_postings = merge_preserved_edits(
        new_postings, existing_postings, key_field="posting_id",
    )

    workbook.companies_tab.clear()
    workbook.companies_tab.write_rows(merged_companies)
    workbook.postings_tab.clear()
    workbook.postings_tab.write_rows(merged_postings)

    archived = archived_companies + archived_postings
    if archived:
        workbook.archived_tab.append_rows(archived)
