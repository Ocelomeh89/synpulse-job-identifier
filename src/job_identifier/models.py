from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class RoleType(str, Enum):
    ENGINEERING = "ENGINEERING"
    DATA_AI = "DATA_AI"
    LEADERSHIP = "LEADERSHIP"
    BUSINESS_OPS = "BUSINESS_OPS"
    OTHER = "OTHER"


class Seniority(str, Enum):
    IC = "IC"
    SENIOR_IC = "SENIOR_IC"
    LEAD = "LEAD"
    DIRECTOR = "DIRECTOR"
    VP_PLUS = "VP_PLUS"


@dataclass(frozen=True)
class Posting:
    posting_id: str
    source: str
    source_url: str
    fetched_at: datetime
    title: str
    company: str
    company_normalized: str
    location: str
    country: str
    posted_date: date
    description: str
    description_excerpt: str
    skill_matches: list[str]
    industry_match: bool
    role_type: RoleType
    seniority: Seniority
    recency_score: float
    seniority_score: float
    score: float
    is_new: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fetched_at"] = self.fetched_at.isoformat()
        d["posted_date"] = self.posted_date.isoformat()
        d["role_type"] = self.role_type.value
        d["seniority"] = self.seniority.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Posting:
        return cls(
            posting_id=d["posting_id"],
            source=d["source"],
            source_url=d["source_url"],
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            title=d["title"],
            company=d["company"],
            company_normalized=d["company_normalized"],
            location=d["location"],
            country=d["country"],
            posted_date=date.fromisoformat(d["posted_date"]),
            description=d["description"],
            description_excerpt=d["description_excerpt"],
            skill_matches=list(d["skill_matches"]),
            industry_match=bool(d["industry_match"]),
            role_type=RoleType(d["role_type"]),
            seniority=Seniority(d["seniority"]),
            recency_score=float(d["recency_score"]),
            seniority_score=float(d["seniority_score"]),
            score=float(d["score"]),
            is_new=bool(d["is_new"]),
        )


@dataclass(frozen=True)
class Secrets:
    serpapi_key: str
    firecrawl_api_key: str
    google_sheets_creds_path: str | None
    google_sheets_creds_json: str | None
    workbook_ids_by_run: dict[str, str]


@dataclass(frozen=True)
class RunSkillConfig:
    hard_match_regex: str
    query_terms: list[str]


@dataclass(frozen=True)
class RunIndustryConfig:
    include_keywords: list[str]
    deny_companies: list[str]


@dataclass(frozen=True)
class ScoreWeights:
    recency: float
    seniority: float


@dataclass(frozen=True)
class EnrichmentConfig:
    firecrawl_min_jd_chars: int


@dataclass(frozen=True)
class OutputConfig:
    companies_tab: str
    postings_tab: str
    archived_tab: str


@dataclass(frozen=True)
class RunConfig:
    name: str
    enabled: bool
    skill: RunSkillConfig
    industry: RunIndustryConfig
    geos: list[str]
    recency_window_days: int
    score_weights: ScoreWeights
    enrichment: EnrichmentConfig
    output: OutputConfig


@dataclass
class RunResult:
    run_id: str
    run_name: str
    started_at: datetime
    finished_at: datetime | None
    status: str  # running | ok | failed | sheet_write_failed
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
