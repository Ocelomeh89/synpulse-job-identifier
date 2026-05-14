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
    c = company.lower()
    return any(d.lower() == c for d in deny_companies)


def apply(postings: list[Posting], cfg: RunConfig, now: datetime) -> list[Posting]:
    out: list[Posting] = []
    for p in postings:
        skill_matches = find_skill_matches(p.description, cfg.skill.hard_match_regex)
        if not skill_matches:
            continue
        if (now.date() - p.posted_date).days > cfg.recency_window_days:
            continue
        if not matches_industry(
            p.title, p.company, p.description, cfg.industry.include_keywords
        ):
            continue
        if is_denied(p.company, cfg.industry.deny_companies):
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
