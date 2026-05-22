from __future__ import annotations
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from job_identifier.models import (
    EnrichmentConfig,
    OutputConfig,
    RunConfig,
    RunIndustryConfig,
    RunSkillConfig,
    ScoreWeights,
    Secrets,
)


class _SkillModel(BaseModel):
    hard_match_regex: str
    query_terms: list[str]


class _IndustryModel(BaseModel):
    include_keywords: list[str]
    deny_companies: list[str] = Field(default_factory=list)
    allow_companies: list[str] = Field(default_factory=list)


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
                allow_companies=r.industry.allow_companies,
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


def load_secrets(run_names: list[str], dotenv_path: Path | None = None) -> Secrets:
    if dotenv_path is None and Path(".env").exists():
        load_dotenv(".env")
    elif dotenv_path is not None:
        load_dotenv(dotenv_path)

    def _required(key: str) -> str:
        val = os.environ.get(key)
        if not val:
            raise RuntimeError(f"Required environment variable {key} is not set")
        return val

    workbook_ids: dict[str, str] = {}
    for name in run_names:
        env_key = f"GSHEET_WORKBOOK_{name.upper()}"
        workbook_ids[name] = _required(env_key)

    creds_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH") or None
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDS_JSON") or None
    if not creds_path and not creds_json:
        raise RuntimeError(
            "One of GOOGLE_SHEETS_CREDS_PATH or GOOGLE_SHEETS_CREDS_JSON is required"
        )

    return Secrets(
        serpapi_key=_required("SERPAPI_KEY"),
        firecrawl_api_key=_required("FIRECRAWL_API_KEY"),
        google_sheets_creds_path=creds_path,
        google_sheets_creds_json=creds_json,
        workbook_ids_by_run=workbook_ids,
    )
