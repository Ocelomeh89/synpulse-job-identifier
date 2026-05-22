from __future__ import annotations
import re
from dataclasses import replace
from datetime import datetime

from job_identifier.models import Posting, RoleType, RunConfig, Seniority


def find_skill_matches(description: str, pattern: str) -> list[str]:
    rx = re.compile(pattern, re.IGNORECASE)
    canonical: set[str] = set()
    for m in rx.finditer(description):
        token = m.group(1) if m.groups() else m.group(0)
        for opt in re.findall(r"[A-Za-z]+", pattern):
            if opt.lower() == token.lower():
                canonical.add(opt)
                break
    return sorted(canonical)


def build_excerpt(description: str, skill_matches: list[str], width: int = 200) -> str:
    if not description:
        return ""
    if not skill_matches:
        return description[:width]
    rx = re.compile(
        r"\b(" + "|".join(re.escape(s) for s in skill_matches) + r")\b",
        re.IGNORECASE,
    )
    m = rx.search(description)
    if not m:
        return description[:width]
    start = max(0, m.start() - width // 2)
    end = min(len(description), start + width)
    snippet = description[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(description) else ""
    return f"{prefix}{snippet}{suffix}"


def classify_role_type(title: str, description: str) -> RoleType:
    text = f"{title} {description}".lower()
    if re.search(r"\b(head of|director|vp|chief|president)\b", text):
        return RoleType.LEADERSHIP
    if re.search(
        r"\b(data scientist|data engineer|ml engineer|machine learning|"
        r"ai engineer|analytics engineer)\b",
        text,
    ):
        return RoleType.DATA_AI
    if re.search(r"\b(engineer|developer|architect|devops|platform|sre)\b", text):
        return RoleType.ENGINEERING
    if re.search(r"\b(analyst|operations|consultant|manager)\b", text):
        return RoleType.BUSINESS_OPS
    return RoleType.OTHER


def classify_seniority(title: str) -> Seniority:
    t = title.lower()
    if re.search(r"\b(vp|chief|president)\b", t):
        return Seniority.VP_PLUS
    if re.search(r"\b(director|head of)\b", t):
        return Seniority.DIRECTOR
    if re.search(r"\b(lead|principal|staff)\b", t):
        return Seniority.LEAD
    if re.search(r"\b(senior|sr\.?)\b", t):
        return Seniority.SENIOR_IC
    return Seniority.IC


def matches_industry(title: str, company: str, description: str, include_keywords: list[str]) -> bool:
    haystack = f"{title} {company} {description}".lower()
    return any(kw.lower() in haystack for kw in include_keywords)


def is_denied(company: str, deny_companies: list[str]) -> bool:
    """True if the company name contains any deny-list entry (case-insensitive).

    Substring match (not exact) so 'System One' denies 'System One Holdings LLC'.
    Keep deny entries specific enough to avoid catching legitimate targets
    (e.g. don't add 'IBM' if it might match 'IBM Insurance Holdings').
    """
    c = company.lower()
    return any(d.lower() in c for d in deny_companies)


def is_allowed(company: str, allow_companies: list[str]) -> bool:
    """True if company is on the allow list (substring match, case-insensitive).

    Allow-list bypasses the industry-keyword gate (the JD may not mention
    insurance terms even though the company is a known target). Deny-list and
    recency still apply.
    """
    c = company.lower()
    return any(a.lower() in c for a in allow_companies)


_TRAILING_NUMBER = re.compile(r"[\s#:_-]+\d+\s*$")


def _base_title(title: str) -> str:
    return _TRAILING_NUMBER.sub("", title.strip())


def collapse_recruiter_variants(postings: list[Posting]) -> list[Posting]:
    """Collapse near-duplicate postings from the same recruiter.

    Staffing firms (Apex Systems, System One, etc.) post the same role with a
    trailing tracking number — "Palantir Platform Engineer 14", "...17", "...32".
    Group by (company_normalized, base_title-with-trailing-digits-stripped) and
    keep the representative with the most recent posted_date (tie-break: longest
    description). Postings whose base_title equals their original title are
    passed through unchanged.
    """
    groups: dict[tuple[str, str], list[Posting]] = {}
    for p in postings:
        key = (p.company_normalized, _base_title(p.title).lower())
        groups.setdefault(key, []).append(p)
    out: list[Posting] = []
    for variants in groups.values():
        if len(variants) == 1:
            out.append(variants[0])
        else:
            variants.sort(key=lambda p: (p.posted_date, len(p.description)), reverse=True)
            out.append(variants[0])
    return out


def apply(postings: list[Posting], cfg: RunConfig, now: datetime) -> list[Posting]:
    out: list[Posting] = []
    for p in postings:
        skill_matches = find_skill_matches(p.description, cfg.skill.hard_match_regex)
        if not skill_matches:
            continue
        if (now.date() - p.posted_date).days > cfg.recency_window_days:
            continue
        if is_denied(p.company, cfg.industry.deny_companies):
            continue
        allowed = is_allowed(p.company, cfg.industry.allow_companies)
        if not allowed and not matches_industry(
            p.title, p.company, p.description, cfg.industry.include_keywords
        ):
            continue

        out.append(
            replace(
                p,
                skill_matches=skill_matches,
                industry_match=True,
                role_type=classify_role_type(p.title, p.description),
                seniority=classify_seniority(p.title),
                description_excerpt=build_excerpt(p.description, skill_matches),
            )
        )
    return out
