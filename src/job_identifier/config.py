from __future__ import annotations
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from job_identifier.models import (
    EnrichmentConfig,
    OutputConfig,
    RunConfig,
    RunIndustryConfig,
    RunSkillConfig,
    ScoreWeights,
)


class _SkillModel(BaseModel):
    hard_match_regex: str
    query_terms: list[str]


class _IndustryModel(BaseModel):
    include_keywords: list[str]
    deny_companies: list[str] = Field(default_factory=list)


class _ScoreWeightsModel(BaseModel):
    recency: float
    seniority: float


class _EnrichmentModel(BaseModel):
    firecrawl_min_jd_chars: int


class _OutputModel(BaseModel):
    companies_tab: str
    postings_tab: str
    archived_tab: str


class _DefaultsModel(BaseModel):
    recency_window_days: int
    score_weights: _ScoreWeightsModel
    enrichment: _EnrichmentModel
    output: _OutputModel


class _RunModel(BaseModel):
    name: str
    enabled: bool
    skill: _SkillModel
    industry: _IndustryModel
    geos: list[str]


class _FileModel(BaseModel):
    defaults: _DefaultsModel
    runs: list[_RunModel]


def load_runs(path: Path) -> list[RunConfig]:
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    data = _FileModel.model_validate(raw)
    return [
        RunConfig(
            name=r.name,
            enabled=r.enabled,
            skill=RunSkillConfig(
                hard_match_regex=r.skill.hard_match_regex,
                query_terms=r.skill.query_terms,
            ),
            industry=RunIndustryConfig(
                include_keywords=r.industry.include_keywords,
                deny_companies=r.industry.deny_companies,
            ),
            geos=r.geos,
            recency_window_days=data.defaults.recency_window_days,
            score_weights=ScoreWeights(
                recency=data.defaults.score_weights.recency,
                seniority=data.defaults.score_weights.seniority,
            ),
            enrichment=EnrichmentConfig(
                firecrawl_min_jd_chars=data.defaults.enrichment.firecrawl_min_jd_chars,
            ),
            output=OutputConfig(
                companies_tab=data.defaults.output.companies_tab,
                postings_tab=data.defaults.output.postings_tab,
                archived_tab=data.defaults.output.archived_tab,
            ),
        )
        for r in data.runs
    ]
