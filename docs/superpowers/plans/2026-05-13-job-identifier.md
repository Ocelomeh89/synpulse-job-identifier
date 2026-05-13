# Job Identifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pipeline that turns public job postings into a sales-trigger list (companies × skill × industry), with a Streamlit UI for triggering runs and a Google Sheet as the editable output surface.

**Architecture:** Pipeline of pure-function stages (`source → normalize → filter → enrich → filter-again → dedupe → score → sink`). Streamlit UI and `typer` CLI both call the same `runner.run()` entry point. SQLite is source of truth for postings + run history; Google Sheets is the human-facing output.

**Tech Stack:** Python 3.11, `pydantic`, `typer`, `httpx`, `google-search-results` (SerpAPI), `firecrawl-py`, `gspread`, `streamlit`, `sqlite-utils`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-05-13-job-identifier-design.md`. Refer back when behavior is ambiguous.

**Multi-agent execution:** Phase 0 is serial. Phase 1 contains five workstreams (A-E) that can be assigned to parallel agents. Phase 2 is serial. Phase 3 can begin once Phase 2 starts. Phase 4 is the final integration test.

---

## Phase 0 — Foundation (serial, single agent)

Every Phase 1 workstream depends on Phase 0. It must complete first.

---

### Task 0.1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore` (overwrites if exists)
- Create: `src/job_identifier/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`
- Create: `config/.gitkeep`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/job_identifier/{sources,sink,enrich,ui/pages,ui/components} \
         tests/fixtures \
         config \
         credentials \
         data/logs
touch src/job_identifier/__init__.py \
      src/job_identifier/sources/__init__.py \
      src/job_identifier/sink/__init__.py \
      src/job_identifier/enrich/__init__.py \
      src/job_identifier/ui/__init__.py \
      src/job_identifier/ui/pages/__init__.py \
      src/job_identifier/ui/components/__init__.py \
      tests/__init__.py \
      tests/fixtures/.gitkeep \
      config/.gitkeep
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "job-identifier"
version = "0.1.0"
description = "Sales-trigger pipeline mining public job postings"
requires-python = ">=3.11"
dependencies = [
    "python-dotenv>=1.0",
    "pydantic>=2.5",
    "pyyaml>=6.0",
    "typer>=0.12",
    "httpx>=0.27",
    "google-search-results>=2.4",
    "firecrawl-py>=1.0",
    "gspread>=6.0",
    "google-auth>=2.30",
    "streamlit>=1.35",
    "sqlite-utils>=3.36",
    "python-ulid>=2.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "ruff>=0.5",
    "mypy>=1.10",
]

[project.scripts]
job-id = "job_identifier.cli:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "e2e: end-to-end tests that run the full pipeline against fixtures",
]
```

- [ ] **Step 3: Write `.env.example`**

```bash
# SerpAPI (https://serpapi.com)
SERPAPI_KEY=your_serpapi_key_here

# Firecrawl (https://firecrawl.dev)
FIRECRAWL_API_KEY=your_firecrawl_key_here

# Google Sheets service account JSON file path
GOOGLE_SHEETS_CREDS_PATH=credentials/service-account.json

# One env var per run, mapping run_name (uppercased) → workbook ID
GSHEET_WORKBOOK_PALANTIR_INSURANCE=replace_with_real_workbook_id
```

- [ ] **Step 4: Write `.gitignore`**

```gitignore
# Secrets
.env
.env.local
credentials/*.json

# Data
data/jobs.db
data/jobs.db-journal
data/logs/*.log

# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
build/
dist/

# Streamlit
.streamlit/secrets.toml

# OS
.DS_Store
```

- [ ] **Step 5: Install deps and verify**

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
python -c "import job_identifier; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/ tests/ config/
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 0.2: Core data models

**Files:**
- Create: `src/job_identifier/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority


def test_posting_is_frozen():
    p = _sample_posting()
    try:
        p.title = "Other"  # type: ignore[misc]
    except Exception as e:
        assert "frozen" in str(e).lower() or "immutable" in str(e).lower()
    else:
        raise AssertionError("Posting should be immutable")


def test_posting_serializes_to_dict():
    p = _sample_posting()
    d = p.to_dict()
    assert d["title"] == "Senior Palantir Foundry Engineer"
    assert d["role_type"] == "ENGINEERING"
    assert d["seniority"] == "SENIOR_IC"
    assert d["posted_date"] == "2026-05-01"


def test_posting_roundtrips_through_dict():
    p = _sample_posting()
    d = p.to_dict()
    p2 = Posting.from_dict(d)
    assert p2 == p


def _sample_posting() -> Posting:
    return Posting(
        posting_id="abc123",
        source="serpapi",
        source_url="https://example.com/job/1",
        fetched_at=datetime(2026, 5, 13, 10, 0, 0),
        title="Senior Palantir Foundry Engineer",
        company="Acme Insurance Inc",
        company_normalized="acme insurance",
        location="New York, NY",
        country="US",
        posted_date=date(2026, 5, 1),
        description="We're hiring a Palantir Foundry engineer...",
        description_excerpt="...Palantir Foundry engineer...",
        skill_matches=["Foundry"],
        industry_match=True,
        role_type=RoleType.ENGINEERING,
        seniority=Seniority.SENIOR_IC,
        recency_score=0.87,
        seniority_score=0.40,
        score=0.69,
        is_new=True,
    )
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_models.py -v
```
Expected: `ImportError: cannot import name 'Posting' from 'job_identifier.models'`.

- [ ] **Step 3: Write `models.py`**

```python
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
    google_sheets_creds_path: str
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_models.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/models.py tests/test_models.py
git commit -m "feat(models): add Posting, RunConfig, Secrets, enums"
```

---

### Task 0.3: Run config loader with pydantic validation

**Files:**
- Create: `src/job_identifier/config.py`
- Create: `config/runs.yaml`
- Create: `tests/test_config_runs.py`

- [ ] **Step 1: Write `config/runs.yaml`**

```yaml
defaults:
  recency_window_days: 90
  score_weights:
    recency: 0.6
    seniority: 0.4
  enrichment:
    firecrawl_min_jd_chars: 500
  output:
    companies_tab: "Companies"
    postings_tab: "Postings"
    archived_tab: "Archived"

runs:
  - name: palantir_insurance
    enabled: true
    skill:
      hard_match_regex: '\b(Foundry|AIP)\b'
      query_terms:
        - '"Palantir Foundry" insurance'
        - '"Palantir AIP" insurance'
        - 'Palantir reinsurance'
    industry:
      include_keywords:
        - insurance
        - insurer
        - carrier
        - reinsurance
        - reinsurer
        - underwriting
        - claims
        - seguros
        - aseguradora
        - reaseguradora
        - suscripción
        - siniestros
      deny_companies:
        - Palantir Technologies
        - Accenture
        - Deloitte
        - IBM
        - Capgemini
        - Cognizant
        - Tata Consultancy
        - Infosys
        - Wipro
    geos: [US, CA, MX, UK, BM]
```

- [ ] **Step 2: Write the failing test**

`tests/test_config_runs.py`:
```python
from pathlib import Path
from job_identifier.config import load_runs


def test_load_palantir_insurance_run():
    runs = load_runs(Path("config/runs.yaml"))
    assert len(runs) == 1
    r = runs[0]
    assert r.name == "palantir_insurance"
    assert r.enabled is True
    assert r.skill.hard_match_regex == r"\b(Foundry|AIP)\b"
    assert "insurance" in r.industry.include_keywords
    assert "seguros" in r.industry.include_keywords
    assert "Palantir Technologies" in r.industry.deny_companies
    assert r.geos == ["US", "CA", "MX", "UK", "BM"]
    assert r.recency_window_days == 90
    assert r.score_weights.recency == 0.6
    assert r.score_weights.seniority == 0.4
    assert r.enrichment.firecrawl_min_jd_chars == 500
    assert r.output.companies_tab == "Companies"
```

- [ ] **Step 3: Run test and verify it fails**

```bash
pytest tests/test_config_runs.py -v
```
Expected: `ImportError: cannot import name 'load_runs'`.

- [ ] **Step 4: Write `config.py`**

```python
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
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_config_runs.py -v
```
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add config/runs.yaml src/job_identifier/config.py tests/test_config_runs.py
git commit -m "feat(config): load and validate runs.yaml via pydantic"
```

---

### Task 0.4: Secrets loader

**Files:**
- Modify: `src/job_identifier/config.py`
- Create: `tests/test_config_secrets.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config_secrets.py`:
```python
from job_identifier.config import load_secrets


def test_load_secrets_from_env(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "sk_serp")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "sk_fc")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", "credentials/sa.json")
    monkeypatch.setenv("GSHEET_WORKBOOK_PALANTIR_INSURANCE", "abc123")

    s = load_secrets(run_names=["palantir_insurance"])
    assert s.serpapi_key == "sk_serp"
    assert s.firecrawl_api_key == "sk_fc"
    assert s.google_sheets_creds_path == "credentials/sa.json"
    assert s.workbook_ids_by_run == {"palantir_insurance": "abc123"}


def test_load_secrets_missing_serpapi_raises(monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", "x")
    monkeypatch.setenv("GSHEET_WORKBOOK_FOO", "x")

    try:
        load_secrets(run_names=["foo"])
    except RuntimeError as e:
        assert "SERPAPI_KEY" in str(e)
    else:
        raise AssertionError("Expected RuntimeError")
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_config_secrets.py -v
```
Expected: `ImportError: cannot import name 'load_secrets'`.

- [ ] **Step 3: Add `load_secrets()` to `config.py`**

Append to `src/job_identifier/config.py`:
```python
import os
from dotenv import load_dotenv
from job_identifier.models import Secrets


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

    return Secrets(
        serpapi_key=_required("SERPAPI_KEY"),
        firecrawl_api_key=_required("FIRECRAWL_API_KEY"),
        google_sheets_creds_path=_required("GOOGLE_SHEETS_CREDS_PATH"),
        workbook_ids_by_run=workbook_ids,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_config_secrets.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/config.py tests/test_config_secrets.py
git commit -m "feat(config): add load_secrets with required-env validation"
```

---

### Task 0.5: Test fixtures and conftest

These fixtures are the contract between Phase 1 workstreams. Get them right.

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/fixtures/raw_serpapi_sample.json`
- Create: `tests/fixtures/normalized_postings_sample.json`
- Create: `tests/fixtures/filtered_postings_sample.json`

- [ ] **Step 1: Write `tests/fixtures/raw_serpapi_sample.json`**

```json
{
  "search_metadata": {
    "status": "Success",
    "google_jobs_url": "https://www.google.com/search?q=palantir+foundry+insurance"
  },
  "jobs_results": [
    {
      "title": "Senior Palantir Foundry Engineer",
      "company_name": "Acme Insurance Inc",
      "location": "New York, NY",
      "via": "via LinkedIn",
      "description": "We are hiring a Senior Palantir Foundry engineer to lead our data platform team. You will work on claims analytics and underwriting workflows in Foundry. Experience with AIP is a plus.",
      "detected_extensions": {
        "posted_at": "5 days ago",
        "schedule_type": "Full-time"
      },
      "share_link": "https://www.google.com/search?ibp=htl;jobs#job_1",
      "apply_options": [
        {"link": "https://linkedin.com/jobs/view/1234"}
      ]
    },
    {
      "title": "Foundry Solutions Architect",
      "company_name": "Hamilton Re Ltd",
      "location": "Hamilton, Bermuda",
      "via": "via Indeed",
      "description": "Hamilton Re is hiring a Foundry Solutions Architect to design our reinsurance data platform. You will own the architecture for our property catastrophe workflows.",
      "detected_extensions": {
        "posted_at": "12 days ago",
        "schedule_type": "Full-time"
      },
      "share_link": "https://www.google.com/search?ibp=htl;jobs#job_2",
      "apply_options": [
        {"link": "https://hamiltonre.com/careers/2"}
      ]
    },
    {
      "title": "Marketing Analyst",
      "company_name": "Generic Marketing Co",
      "location": "Toronto, ON",
      "via": "via Indeed",
      "description": "Looking for a marketing analyst. No tech experience required. We work with creative agencies.",
      "detected_extensions": {
        "posted_at": "3 days ago",
        "schedule_type": "Full-time"
      },
      "share_link": "https://www.google.com/search?ibp=htl;jobs#job_3",
      "apply_options": [
        {"link": "https://indeed.com/jobs/3"}
      ]
    },
    {
      "title": "Senior Engineer - Palantir Foundry",
      "company_name": "Accenture",
      "location": "Chicago, IL",
      "via": "via Glassdoor",
      "description": "Accenture is hiring a senior engineer with Palantir Foundry experience. You will deliver Foundry implementations for our insurance clients.",
      "detected_extensions": {
        "posted_at": "8 days ago"
      },
      "share_link": "https://www.google.com/search?ibp=htl;jobs#job_4",
      "apply_options": [
        {"link": "https://accenture.com/careers/4"}
      ]
    }
  ]
}
```

- [ ] **Step 2: Write `tests/fixtures/normalized_postings_sample.json`**

This is what `normalize()` should output for the raw fixture above, **before** filtering. Fetched_at and posted_date use 2026-05-13 as "today" for deterministic tests.

```json
[
  {
    "posting_id": "0e7d8c2a5b4f6c1e9d8a7b6c5e4d3f2a1b0c9d8e",
    "source": "serpapi",
    "source_url": "https://linkedin.com/jobs/view/1234",
    "fetched_at": "2026-05-13T10:00:00",
    "title": "Senior Palantir Foundry Engineer",
    "company": "Acme Insurance Inc",
    "company_normalized": "acme insurance",
    "location": "New York, NY",
    "country": "US",
    "posted_date": "2026-05-08",
    "description": "We are hiring a Senior Palantir Foundry engineer to lead our data platform team. You will work on claims analytics and underwriting workflows in Foundry. Experience with AIP is a plus.",
    "description_excerpt": "",
    "skill_matches": [],
    "industry_match": false,
    "role_type": "OTHER",
    "seniority": "IC",
    "recency_score": 0.0,
    "seniority_score": 0.0,
    "score": 0.0,
    "is_new": false
  },
  {
    "posting_id": "1f8e9d3b6c5a7d2e0e9b8c7d6f5e4a3b2c1d0e9f",
    "source": "serpapi",
    "source_url": "https://hamiltonre.com/careers/2",
    "fetched_at": "2026-05-13T10:00:00",
    "title": "Foundry Solutions Architect",
    "company": "Hamilton Re Ltd",
    "company_normalized": "hamilton re",
    "location": "Hamilton, Bermuda",
    "country": "BM",
    "posted_date": "2026-05-01",
    "description": "Hamilton Re is hiring a Foundry Solutions Architect to design our reinsurance data platform. You will own the architecture for our property catastrophe workflows.",
    "description_excerpt": "",
    "skill_matches": [],
    "industry_match": false,
    "role_type": "OTHER",
    "seniority": "IC",
    "recency_score": 0.0,
    "seniority_score": 0.0,
    "score": 0.0,
    "is_new": false
  },
  {
    "posting_id": "2a9f0e4c7d6b8e3f1f0c9d8e7g6f5b4c3d2e1f0a",
    "source": "serpapi",
    "source_url": "https://indeed.com/jobs/3",
    "fetched_at": "2026-05-13T10:00:00",
    "title": "Marketing Analyst",
    "company": "Generic Marketing Co",
    "company_normalized": "generic marketing co",
    "location": "Toronto, ON",
    "country": "CA",
    "posted_date": "2026-05-10",
    "description": "Looking for a marketing analyst. No tech experience required. We work with creative agencies.",
    "description_excerpt": "",
    "skill_matches": [],
    "industry_match": false,
    "role_type": "OTHER",
    "seniority": "IC",
    "recency_score": 0.0,
    "seniority_score": 0.0,
    "score": 0.0,
    "is_new": false
  },
  {
    "posting_id": "3b0a1f5d8e7c9f4a2a1d0e9f8h7g6c5d4e3f2a1b",
    "source": "serpapi",
    "source_url": "https://accenture.com/careers/4",
    "fetched_at": "2026-05-13T10:00:00",
    "title": "Senior Engineer - Palantir Foundry",
    "company": "Accenture",
    "company_normalized": "accenture",
    "location": "Chicago, IL",
    "country": "US",
    "posted_date": "2026-05-05",
    "description": "Accenture is hiring a senior engineer with Palantir Foundry experience. You will deliver Foundry implementations for our insurance clients.",
    "description_excerpt": "",
    "skill_matches": [],
    "industry_match": false,
    "role_type": "OTHER",
    "seniority": "IC",
    "recency_score": 0.0,
    "seniority_score": 0.0,
    "score": 0.0,
    "is_new": false
  }
]
```

Note: `posting_id` values above are illustrative placeholders. The test for `normalize()` computes them deterministically from the hash function; assertions in WS A's tests use the hash function directly rather than these literal strings.

- [ ] **Step 3: Write `tests/fixtures/filtered_postings_sample.json`**

This is the expected output of `filter.apply()` on the normalized fixture above with the `palantir_insurance` config. Postings 3 (no skill match, no industry match) and 4 (in deny-list) drop. Postings 1 and 2 remain with classifications populated.

```json
[
  {
    "company_normalized": "acme insurance",
    "title": "Senior Palantir Foundry Engineer",
    "country": "US",
    "skill_matches": ["Foundry", "AIP"],
    "industry_match": true,
    "role_type": "ENGINEERING",
    "seniority": "SENIOR_IC"
  },
  {
    "company_normalized": "hamilton re",
    "title": "Foundry Solutions Architect",
    "country": "BM",
    "skill_matches": ["Foundry"],
    "industry_match": true,
    "role_type": "ENGINEERING",
    "seniority": "IC"
  }
]
```

(Filter fixture is reduced to the fields tests assert against — keeps tests robust to unrelated `Posting` evolutions.)

- [ ] **Step 4: Write `tests/conftest.py`**

```python
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw_serpapi_response() -> dict:
    return json.loads((FIXTURES / "raw_serpapi_sample.json").read_text())


@pytest.fixture
def normalized_postings_json() -> list[dict]:
    return json.loads((FIXTURES / "normalized_postings_sample.json").read_text())


@pytest.fixture
def filtered_postings_expected() -> list[dict]:
    return json.loads((FIXTURES / "filtered_postings_sample.json").read_text())


@pytest.fixture
def fixed_now():
    """Deterministic 'today' for tests: 2026-05-13T10:00:00."""
    from datetime import datetime
    return datetime(2026, 5, 13, 10, 0, 0)
```

- [ ] **Step 5: Verify fixtures load**

```bash
pytest --collect-only tests/conftest.py
python -c "import json; json.loads(open('tests/fixtures/raw_serpapi_sample.json').read())"
python -c "import json; json.loads(open('tests/fixtures/normalized_postings_sample.json').read())"
python -c "import json; json.loads(open('tests/fixtures/filtered_postings_sample.json').read())"
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/fixtures/
git commit -m "test: add SerpAPI/normalized/filtered fixtures for Phase 1 workstreams"
```

---

**Phase 0 exit criteria:**
- `pytest tests/` runs and all tests pass.
- `python -c "from job_identifier.models import Posting; from job_identifier.config import load_runs, load_secrets"` works.
- The three fixture files exist and parse as valid JSON.

After this, Phase 1 workstreams A through E can be assigned to parallel agents.

---

## Phase 1A — Source + Normalize

**Owns:** `sources/serpapi_jobs.py`, `normalize.py`, related tests.
**Depends on:** `models`, `config`.
**Verifies via:** `normalize()` output matches `normalized_postings_sample.json` semantics.

---

### Task 1A.1: Country mapping helper

**Files:**
- Create: `src/job_identifier/country.py`
- Create: `tests/test_country.py`

- [ ] **Step 1: Write the failing test**

`tests/test_country.py`:
```python
from job_identifier.country import country_from_location


def test_us_locations():
    assert country_from_location("New York, NY") == "US"
    assert country_from_location("Chicago, IL") == "US"
    assert country_from_location("Remote, United States") == "US"


def test_canada_locations():
    assert country_from_location("Toronto, ON") == "CA"
    assert country_from_location("Vancouver, BC, Canada") == "CA"


def test_uk_locations():
    assert country_from_location("London, UK") == "GB"
    assert country_from_location("Manchester, England") == "GB"


def test_bermuda_locations():
    assert country_from_location("Hamilton, Bermuda") == "BM"


def test_mexico_locations():
    assert country_from_location("Ciudad de México, CDMX") == "MX"
    assert country_from_location("México, Mexico") == "MX"


def test_unknown_location_returns_xx():
    assert country_from_location("Atlantis") == "XX"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_country.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `country.py`**

```python
US_STATE_ABBREVS = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC",
}
CA_PROVINCE_ABBREVS = {"ON","QC","BC","AB","MB","SK","NS","NB","NL","PE","NT","YT","NU"}


def country_from_location(loc: str) -> str:
    s = loc.lower()
    if "bermuda" in s:
        return "BM"
    if any(t in s for t in ("united kingdom", "england", "scotland", "wales", "uk", ", uk")):
        return "GB"
    if any(t in s for t in ("canada", "canadá")):
        return "CA"
    if any(t in s for t in ("mexico", "méxico", "cdmx")):
        return "MX"
    if "united states" in s or "usa" in s or ", us" in s:
        return "US"

    parts = [p.strip().upper() for p in loc.split(",")]
    for p in parts:
        if p in CA_PROVINCE_ABBREVS:
            return "CA"
        if p in US_STATE_ABBREVS:
            return "US"
    return "XX"
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_country.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/country.py tests/test_country.py
git commit -m "feat(country): map location strings to ISO-2 codes"
```

---

### Task 1A.2: Normalize raw SerpAPI → Posting

**Files:**
- Create: `src/job_identifier/normalize.py`
- Create: `tests/test_normalize.py`

- [ ] **Step 1: Write the failing test**

`tests/test_normalize.py`:
```python
from datetime import datetime, date
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
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_normalize.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `normalize.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_normalize.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/normalize.py tests/test_normalize.py
git commit -m "feat(normalize): map raw SerpAPI jobs to Posting dataclass"
```

---

### Task 1A.3: SerpAPI source client (mocked HTTP)

**Files:**
- Create: `src/job_identifier/sources/serpapi_jobs.py`
- Create: `tests/test_source_serpapi.py`

- [ ] **Step 1: Write the failing test**

`tests/test_source_serpapi.py`:
```python
from unittest.mock import MagicMock

import pytest
from job_identifier.sources.serpapi_jobs import fetch_jobs
from job_identifier.models import (
    EnrichmentConfig, OutputConfig, RunConfig, RunIndustryConfig,
    RunSkillConfig, ScoreWeights,
)


@pytest.fixture
def run_config():
    return RunConfig(
        name="palantir_insurance",
        enabled=True,
        skill=RunSkillConfig(
            hard_match_regex=r"\b(Foundry|AIP)\b",
            query_terms=['"Palantir Foundry" insurance'],
        ),
        industry=RunIndustryConfig(include_keywords=["insurance"], deny_companies=[]),
        geos=["US"],
        recency_window_days=90,
        score_weights=ScoreWeights(recency=0.6, seniority=0.4),
        enrichment=EnrichmentConfig(firecrawl_min_jd_chars=500),
        output=OutputConfig(
            companies_tab="Companies", postings_tab="Postings", archived_tab="Archived"
        ),
    )


def test_fetch_jobs_calls_serpapi_per_geo_and_query(run_config, monkeypatch):
    mock_search = MagicMock()
    mock_search.return_value.get_dict.return_value = {"jobs_results": []}
    monkeypatch.setattr(
        "job_identifier.sources.serpapi_jobs.GoogleSearch", mock_search
    )
    fetch_jobs(run_config, api_key="sk_test")
    assert mock_search.call_count == 1  # 1 geo × 1 query
    params = mock_search.call_args.args[0]
    assert params["engine"] == "google_jobs"
    assert params["q"] == '"Palantir Foundry" insurance'
    assert params["api_key"] == "sk_test"


def test_fetch_jobs_aggregates_results_across_geos(run_config, monkeypatch):
    run_config = RunConfig(
        **{**run_config.__dict__, "geos": ["US", "CA"]}
    )
    mock_search = MagicMock()
    mock_search.return_value.get_dict.return_value = {
        "jobs_results": [{"title": "X", "company_name": "Y"}]
    }
    monkeypatch.setattr(
        "job_identifier.sources.serpapi_jobs.GoogleSearch", mock_search
    )
    results = fetch_jobs(run_config, api_key="sk_test")
    assert mock_search.call_count == 2  # 2 geos × 1 query
    assert len(results) == 2


def test_fetch_jobs_combines_response_dicts(run_config, monkeypatch):
    """Returns the same shape as a single SerpAPI response (jobs_results list)."""
    mock_search = MagicMock()
    mock_search.return_value.get_dict.return_value = {
        "jobs_results": [
            {"title": "A", "company_name": "Acme"},
            {"title": "B", "company_name": "Beta"},
        ]
    }
    monkeypatch.setattr(
        "job_identifier.sources.serpapi_jobs.GoogleSearch", mock_search
    )
    results = fetch_jobs(run_config, api_key="sk_test")
    assert len(results) == 1
    assert "jobs_results" in results[0]
    assert len(results[0]["jobs_results"]) == 2
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_source_serpapi.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `sources/serpapi_jobs.py`**

```python
from __future__ import annotations
import logging
import time
from typing import Any

from serpapi import GoogleSearch

from job_identifier.models import RunConfig

log = logging.getLogger(__name__)


_GEO_TO_GOOGLE_LOCATION = {
    "US": "United States",
    "CA": "Canada",
    "MX": "Mexico",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "BM": "Bermuda",
}


def _fetch_one(query: str, location: str, api_key: str, max_pages: int = 5) -> dict:
    """Fetch one (query × location) combination with pagination, return one merged dict."""
    all_jobs: list[dict] = []
    params: dict[str, Any] = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "api_key": api_key,
    }
    for _ in range(max_pages):
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = GoogleSearch(params).get_dict()
                break
            except Exception as e:
                last_error = e
                time.sleep((attempt + 1) ** 2)
        else:
            raise RuntimeError(f"SerpAPI failed after 3 attempts: {last_error}")

        jobs = response.get("jobs_results", [])
        all_jobs.extend(jobs)
        token = response.get("serpapi_pagination", {}).get("next_page_token")
        if not token:
            break
        params["next_page_token"] = token

    return {"jobs_results": all_jobs}


def fetch_jobs(run_config: RunConfig, api_key: str) -> list[dict]:
    """Returns one response dict per (geo × query_term)."""
    results: list[dict] = []
    for geo in run_config.geos:
        location = _GEO_TO_GOOGLE_LOCATION.get(geo)
        if not location:
            log.warning("Unknown geo %s, skipping", geo)
            continue
        for query in run_config.skill.query_terms:
            log.info("Fetching geo=%s query=%s", geo, query)
            response = _fetch_one(query, location, api_key)
            results.append(response)
    return results
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_source_serpapi.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/sources/serpapi_jobs.py tests/test_source_serpapi.py
git commit -m "feat(source): SerpAPI Google Jobs client with retry + pagination"
```

---

## Phase 1B — Filter + Score

**Owns:** `filter.py`, `score.py`, related tests.
**Depends on:** `models`, `config`.
**Verifies via:** filter output matches `filtered_postings_sample.json`; score is deterministic.

---

### Task 1B.1: Skill regex matcher and excerpt builder

**Files:**
- Create: `src/job_identifier/filter.py`
- Create: `tests/test_filter_skill.py`

- [ ] **Step 1: Write the failing test**

`tests/test_filter_skill.py`:
```python
from job_identifier.filter import find_skill_matches, build_excerpt


def test_find_skill_matches_foundry_only():
    desc = "We use Palantir Foundry for our data platform."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert matches == ["Foundry"]


def test_find_skill_matches_both():
    desc = "Foundry and AIP experience required."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert set(matches) == {"Foundry", "AIP"}
    # Deterministic order:
    assert matches == sorted(matches)


def test_find_skill_matches_word_boundary():
    desc = "Foundryville Pizza and FoundryName Co."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert matches == []


def test_find_skill_matches_case_insensitive():
    desc = "We need foundry experience and aip skills."
    matches = find_skill_matches(desc, r"\b(Foundry|AIP)\b")
    assert set(matches) == {"Foundry", "AIP"}


def test_build_excerpt_centers_on_first_match():
    desc = "A" * 300 + " Foundry " + "B" * 300
    excerpt = build_excerpt(desc, ["Foundry"], width=200)
    assert "Foundry" in excerpt
    assert len(excerpt) <= 200 + 10  # ~200 plus ellipsis padding


def test_build_excerpt_no_matches_returns_head():
    desc = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    excerpt = build_excerpt(desc, [], width=20)
    assert excerpt.startswith("Lorem")
    assert len(excerpt) <= 25
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_filter_skill.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `filter.py` (partial)**

```python
from __future__ import annotations
import re


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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_filter_skill.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/filter.py tests/test_filter_skill.py
git commit -m "feat(filter): skill regex match + excerpt builder"
```

---

### Task 1B.2: Role type and seniority classification

**Files:**
- Modify: `src/job_identifier/filter.py`
- Create: `tests/test_filter_classify.py`

- [ ] **Step 1: Write the failing test**

`tests/test_filter_classify.py`:
```python
from job_identifier.filter import classify_role_type, classify_seniority
from job_identifier.models import RoleType, Seniority


def test_role_type_engineering():
    assert classify_role_type("Senior Software Engineer", "...") == RoleType.ENGINEERING
    assert classify_role_type("Solutions Architect", "DevOps work") == RoleType.ENGINEERING


def test_role_type_data_ai():
    assert classify_role_type("Data Scientist", "...") == RoleType.DATA_AI
    assert classify_role_type("ML Engineer", "...") == RoleType.DATA_AI
    assert classify_role_type("Senior Data Engineer", "...") == RoleType.DATA_AI


def test_role_type_leadership():
    assert classify_role_type("Head of Data", "...") == RoleType.LEADERSHIP
    assert classify_role_type("VP Engineering", "...") == RoleType.LEADERSHIP
    assert classify_role_type("Director of Foundry", "...") == RoleType.LEADERSHIP


def test_role_type_business_ops():
    assert classify_role_type("Business Analyst", "...") == RoleType.BUSINESS_OPS
    assert classify_role_type("Operations Manager", "...") == RoleType.BUSINESS_OPS


def test_role_type_other_fallback():
    assert classify_role_type("Designer", "...") == RoleType.OTHER


def test_seniority_vp_plus():
    assert classify_seniority("VP of Data") == Seniority.VP_PLUS
    assert classify_seniority("Chief Data Officer") == Seniority.VP_PLUS


def test_seniority_director():
    assert classify_seniority("Director, Data Platform") == Seniority.DIRECTOR
    assert classify_seniority("Head of Engineering") == Seniority.DIRECTOR


def test_seniority_lead():
    assert classify_seniority("Lead Engineer") == Seniority.LEAD
    assert classify_seniority("Principal Architect") == Seniority.LEAD
    assert classify_seniority("Staff Engineer") == Seniority.LEAD


def test_seniority_senior_ic():
    assert classify_seniority("Senior Software Engineer") == Seniority.SENIOR_IC
    assert classify_seniority("Sr. Data Scientist") == Seniority.SENIOR_IC


def test_seniority_ic_fallback():
    assert classify_seniority("Software Engineer") == Seniority.IC
    assert classify_seniority("Data Analyst") == Seniority.IC
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_filter_classify.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Add classifiers to `filter.py`**

Append to `src/job_identifier/filter.py`:
```python
from job_identifier.models import RoleType, Seniority


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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_filter_classify.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/filter.py tests/test_filter_classify.py
git commit -m "feat(filter): role_type + seniority classifiers"
```

---

### Task 1B.3: Industry and deny-list match

**Files:**
- Modify: `src/job_identifier/filter.py`
- Create: `tests/test_filter_industry.py`

- [ ] **Step 1: Write the failing test**

`tests/test_filter_industry.py`:
```python
from job_identifier.filter import matches_industry, is_denied


def test_industry_match_english():
    kw = ["insurance", "reinsurance"]
    assert matches_industry("Senior Engineer", "Acme Co", "We do insurance.", kw) is True
    assert matches_industry("Underwriting Analyst", "Re Co", "...", kw) is False


def test_industry_match_company_name():
    kw = ["insurance"]
    assert matches_industry("Engineer", "Acme Insurance", "Just code.", kw) is True


def test_industry_match_title():
    kw = ["insurance"]
    assert matches_industry("Senior Insurance Engineer", "Acme", "...", kw) is True


def test_industry_match_spanish():
    kw = ["seguros", "aseguradora"]
    assert matches_industry("Ingeniero", "Aseguradora MX", "Trabajamos en seguros.", kw) is True


def test_industry_no_match():
    kw = ["insurance"]
    assert matches_industry("Marketing", "Pets R Us", "We love pets.", kw) is False


def test_is_denied_exact():
    deny = ["Palantir Technologies", "Accenture"]
    assert is_denied("Palantir Technologies", deny) is True
    assert is_denied("Accenture", deny) is True
    assert is_denied("Acme Insurance", deny) is False


def test_is_denied_case_insensitive():
    deny = ["accenture"]
    assert is_denied("ACCENTURE", deny) is True
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_filter_industry.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Add industry + deny logic to `filter.py`**

Append to `src/job_identifier/filter.py`:
```python
def matches_industry(title: str, company: str, description: str, include_keywords: list[str]) -> bool:
    haystack = f"{title} {company} {description}".lower()
    return any(kw.lower() in haystack for kw in include_keywords)


def is_denied(company: str, deny_companies: list[str]) -> bool:
    c = company.lower()
    return any(d.lower() == c for d in deny_companies)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_filter_industry.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/filter.py tests/test_filter_industry.py
git commit -m "feat(filter): industry keyword + deny-list match"
```

---

### Task 1B.4: `filter.apply()` composition

**Files:**
- Modify: `src/job_identifier/filter.py`
- Create: `tests/test_filter_apply.py`

- [ ] **Step 1: Write the failing test**

`tests/test_filter_apply.py`:
```python
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
from job_identifier.filter import apply as filter_apply
from job_identifier.models import (
    EnrichmentConfig, OutputConfig, Posting, RoleType, RunConfig,
    RunIndustryConfig, RunSkillConfig, ScoreWeights, Seniority, OutputConfig,
)


def _config():
    return RunConfig(
        name="palantir_insurance",
        enabled=True,
        skill=RunSkillConfig(
            hard_match_regex=r"\b(Foundry|AIP)\b",
            query_terms=[],
        ),
        industry=RunIndustryConfig(
            include_keywords=["insurance", "reinsurance"],
            deny_companies=["Accenture", "Palantir Technologies"],
        ),
        geos=["US"],
        recency_window_days=90,
        score_weights=ScoreWeights(recency=0.6, seniority=0.4),
        enrichment=EnrichmentConfig(firecrawl_min_jd_chars=500),
        output=OutputConfig(
            companies_tab="Companies", postings_tab="Postings", archived_tab="Archived"
        ),
    )


def _posting(**overrides) -> Posting:
    base = Posting(
        posting_id="p1",
        source="serpapi",
        source_url="https://x.com",
        fetched_at=datetime(2026, 5, 13),
        title="Senior Palantir Foundry Engineer",
        company="Acme Insurance",
        company_normalized="acme insurance",
        location="New York, NY",
        country="US",
        posted_date=date(2026, 5, 1),
        description="We need a Foundry engineer for our insurance platform.",
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
    for k, v in overrides.items():
        base = replace(base, **{k: v})
    return base


def test_drops_no_skill_match():
    posting = _posting(description="Marketing role, no tech.")
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_drops_no_industry_match():
    posting = _posting(
        title="Foundry Engineer",
        description="We build Foundry for healthcare.",
        company="Health Co",
        company_normalized="health co",
    )
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_drops_too_old():
    posting = _posting(posted_date=date(2026, 1, 1))  # >90 days from 2026-05-13
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_drops_denied_company():
    posting = _posting(
        company="Accenture",
        company_normalized="accenture",
        description="Foundry consulting for insurance clients.",
    )
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert out == []


def test_keeps_valid_posting_with_classification():
    posting = _posting()
    out = filter_apply([posting], _config(), now=datetime(2026, 5, 13))
    assert len(out) == 1
    p = out[0]
    assert p.skill_matches == ["Foundry"]
    assert p.industry_match is True
    assert p.role_type == RoleType.ENGINEERING
    assert p.seniority == Seniority.SENIOR_IC
    assert p.description_excerpt != ""
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_filter_apply.py -v
```
Expected: `ImportError: cannot import name 'apply'`.

- [ ] **Step 3: Add `apply()` to `filter.py`**

Append to `src/job_identifier/filter.py`:
```python
from dataclasses import replace
from datetime import datetime

from job_identifier.models import Posting, RunConfig


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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_filter_apply.py -v
```
Expected: pass.

- [ ] **Step 5: Run all filter tests**

```bash
pytest tests/test_filter_skill.py tests/test_filter_classify.py tests/test_filter_industry.py tests/test_filter_apply.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/job_identifier/filter.py tests/test_filter_apply.py
git commit -m "feat(filter): apply() composes hard filters and classification"
```

---

### Task 1B.5: Recency + seniority + combined score

**Files:**
- Create: `src/job_identifier/score.py`
- Create: `tests/test_score.py`

- [ ] **Step 1: Write the failing test**

`tests/test_score.py`:
```python
from dataclasses import replace
from datetime import date, datetime
import pytest
from job_identifier.score import (
    recency_score, seniority_score, combined, apply as score_apply,
)
from job_identifier.models import (
    EnrichmentConfig, OutputConfig, Posting, RoleType, RunConfig,
    RunIndustryConfig, RunSkillConfig, ScoreWeights, Seniority,
)


def test_recency_score_fresh_posting():
    posted = date(2026, 5, 12)
    now = datetime(2026, 5, 13)
    assert recency_score(posted, now, window_days=90) == pytest.approx(89.0 / 90.0)


def test_recency_score_at_window_edge():
    posted = date(2026, 2, 12)  # 90 days before 2026-05-13
    now = datetime(2026, 5, 13)
    assert recency_score(posted, now, window_days=90) == pytest.approx(0.0)


def test_recency_score_outside_window_clamped_to_zero():
    posted = date(2025, 1, 1)
    now = datetime(2026, 5, 13)
    assert recency_score(posted, now, window_days=90) == 0.0


def test_seniority_score_table():
    assert seniority_score(Seniority.IC) == 0.20
    assert seniority_score(Seniority.SENIOR_IC) == 0.40
    assert seniority_score(Seniority.LEAD) == 0.60
    assert seniority_score(Seniority.DIRECTOR) == 0.85
    assert seniority_score(Seniority.VP_PLUS) == 1.00


def test_combined():
    weights = ScoreWeights(recency=0.6, seniority=0.4)
    assert combined(1.0, 1.0, weights) == pytest.approx(1.0)
    assert combined(0.5, 0.5, weights) == pytest.approx(0.5)
    assert combined(1.0, 0.0, weights) == pytest.approx(0.6)


def test_apply_writes_scores_to_postings():
    cfg = RunConfig(
        name="x", enabled=True,
        skill=RunSkillConfig(hard_match_regex="x", query_terms=[]),
        industry=RunIndustryConfig(include_keywords=[], deny_companies=[]),
        geos=[], recency_window_days=90,
        score_weights=ScoreWeights(recency=0.6, seniority=0.4),
        enrichment=EnrichmentConfig(firecrawl_min_jd_chars=500),
        output=OutputConfig(companies_tab="C", postings_tab="P", archived_tab="A"),
    )
    p = Posting(
        posting_id="x", source="s", source_url="u",
        fetched_at=datetime(2026, 5, 13),
        title="t", company="c", company_normalized="c",
        location="l", country="US", posted_date=date(2026, 5, 12),
        description="d", description_excerpt="",
        skill_matches=["Foundry"], industry_match=True,
        role_type=RoleType.ENGINEERING, seniority=Seniority.VP_PLUS,
        recency_score=0.0, seniority_score=0.0, score=0.0, is_new=False,
    )
    [scored] = score_apply([p], cfg, now=datetime(2026, 5, 13))
    assert scored.recency_score == pytest.approx(89.0 / 90.0)
    assert scored.seniority_score == 1.0
    assert scored.score == pytest.approx(0.6 * (89.0 / 90.0) + 0.4 * 1.0)
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_score.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `score.py`**

```python
from __future__ import annotations
from dataclasses import replace
from datetime import date, datetime

from job_identifier.models import (
    Posting, RunConfig, ScoreWeights, Seniority,
)


_SENIORITY_SCORE = {
    Seniority.IC: 0.20,
    Seniority.SENIOR_IC: 0.40,
    Seniority.LEAD: 0.60,
    Seniority.DIRECTOR: 0.85,
    Seniority.VP_PLUS: 1.00,
}


def recency_score(posted_date: date, now: datetime, window_days: int) -> float:
    days = (now.date() - posted_date).days
    if days >= window_days:
        return 0.0
    if days < 0:
        return 1.0
    return 1.0 - (days / window_days)


def seniority_score(s: Seniority) -> float:
    return _SENIORITY_SCORE[s]


def combined(recency: float, seniority: float, weights: ScoreWeights) -> float:
    return weights.recency * recency + weights.seniority * seniority


def apply(postings: list[Posting], cfg: RunConfig, now: datetime) -> list[Posting]:
    out: list[Posting] = []
    for p in postings:
        r = recency_score(p.posted_date, now, cfg.recency_window_days)
        s = seniority_score(p.seniority)
        c = combined(r, s, cfg.score_weights)
        out.append(replace(p, recency_score=r, seniority_score=s, score=c))
    return out
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_score.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/score.py tests/test_score.py
git commit -m "feat(score): recency-decay + seniority-bucket combined score"
```

---

## Phase 1C — Store + Dedupe + SQLite sink

**Owns:** `store.py`, `dedupe.py`, `sink/sqlite.py`, related tests.
**Depends on:** `models`.

---

### Task 1C.1: SQLite schema and `Store` class

**Files:**
- Create: `src/job_identifier/store.py`
- Create: `tests/test_store_schema.py`

- [ ] **Step 1: Write the failing test**

`tests/test_store_schema.py`:
```python
from job_identifier.store import Store


def test_store_initializes_schema():
    store = Store(":memory:")
    store.init_schema()
    tables = {t["name"] for t in store.db["sqlite_master"].rows}
    assert {"postings", "runs", "posting_run_link"}.issubset(tables)


def test_store_init_is_idempotent():
    store = Store(":memory:")
    store.init_schema()
    store.init_schema()  # second call must not fail
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_store_schema.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `store.py`**

```python
from __future__ import annotations
from pathlib import Path

from sqlite_utils import Database


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS postings (
  posting_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  run_name TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  config_snapshot TEXT NOT NULL,
  summary TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS posting_run_link (
  run_id TEXT NOT NULL,
  posting_id TEXT NOT NULL,
  is_new INTEGER NOT NULL,
  score REAL,
  PRIMARY KEY (run_id, posting_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_name_started ON runs(run_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_link_run ON posting_run_link(run_id);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = Database(path)

    def init_schema(self) -> None:
        self.db.executescript(_SCHEMA_SQL)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_store_schema.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/store.py tests/test_store_schema.py
git commit -m "feat(store): SQLite schema for postings, runs, posting_run_link"
```

---

### Task 1C.2: Posting upsert + lookup

**Files:**
- Modify: `src/job_identifier/store.py`
- Create: `tests/test_store_postings.py`

- [ ] **Step 1: Write the failing test**

`tests/test_store_postings.py`:
```python
from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.store import Store


def _posting() -> Posting:
    return Posting(
        posting_id="abc",
        source="serpapi",
        source_url="https://x.com",
        fetched_at=datetime(2026, 5, 13, 10, 0, 0),
        title="Engineer",
        company="Acme",
        company_normalized="acme",
        location="NYC",
        country="US",
        posted_date=date(2026, 5, 1),
        description="d",
        description_excerpt="",
        skill_matches=["Foundry"],
        industry_match=True,
        role_type=RoleType.ENGINEERING,
        seniority=Seniority.IC,
        recency_score=0.5,
        seniority_score=0.2,
        score=0.38,
        is_new=False,
    )


def test_upsert_new_posting_marks_is_new():
    store = Store(":memory:")
    store.init_schema()
    p = _posting()
    is_new = store.upsert_posting(p, seen_at=datetime(2026, 5, 13, 10, 0, 0))
    assert is_new is True
    rows = list(store.db["postings"].rows)
    assert len(rows) == 1
    assert rows[0]["posting_id"] == "abc"


def test_upsert_existing_posting_returns_false():
    store = Store(":memory:")
    store.init_schema()
    p = _posting()
    store.upsert_posting(p, seen_at=datetime(2026, 5, 13))
    is_new = store.upsert_posting(p, seen_at=datetime(2026, 5, 14))
    assert is_new is False
    rows = list(store.db["postings"].rows)
    assert len(rows) == 1
    assert rows[0]["last_seen_at"].startswith("2026-05-14")


def test_lookup_posting_returns_payload():
    store = Store(":memory:")
    store.init_schema()
    p = _posting()
    store.upsert_posting(p, seen_at=datetime(2026, 5, 13))
    assert store.posting_exists("abc") is True
    assert store.posting_exists("xyz") is False
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_store_postings.py -v
```
Expected: `AttributeError: 'Store' object has no attribute 'upsert_posting'`.

- [ ] **Step 3: Add upsert and lookup to `store.py`**

Append to `src/job_identifier/store.py`:
```python
import json
from datetime import datetime
from job_identifier.models import Posting


def upsert_posting(self, posting: Posting, seen_at: datetime) -> bool:
    """Returns True if newly inserted, False if already existed."""
    ts = seen_at.isoformat()
    row = self.db["postings"].get(posting.posting_id) if posting.posting_id in self.db["postings"] else None
    if row is None:
        self.db["postings"].insert({
            "posting_id": posting.posting_id,
            "payload": json.dumps(posting.to_dict()),
            "first_seen_at": ts,
            "last_seen_at": ts,
        }, pk="posting_id")
        return True
    self.db["postings"].update(posting.posting_id, {
        "payload": json.dumps(posting.to_dict()),
        "last_seen_at": ts,
    })
    return False


def posting_exists(self, posting_id: str) -> bool:
    try:
        self.db["postings"].get(posting_id)
        return True
    except Exception:
        return False


Store.upsert_posting = upsert_posting
Store.posting_exists = posting_exists
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_store_postings.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/store.py tests/test_store_postings.py
git commit -m "feat(store): upsert + lookup for postings"
```

---

### Task 1C.3: Run + link CRUD

**Files:**
- Modify: `src/job_identifier/store.py`
- Create: `tests/test_store_runs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_store_runs.py`:
```python
from datetime import datetime
from job_identifier.store import Store


def test_record_run_creates_row():
    store = Store(":memory:")
    store.init_schema()
    store.record_run(
        run_id="run_abc",
        run_name="palantir_insurance",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok",
        config_snapshot={"name": "palantir_insurance"},
        summary={"postings": 12, "new": 4},
        error=None,
    )
    rows = list(store.db["runs"].rows)
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert "palantir_insurance" in rows[0]["config_snapshot"]


def test_link_posting_to_run():
    store = Store(":memory:")
    store.init_schema()
    store.link_posting_to_run(
        run_id="run_abc", posting_id="p1", is_new=True, score=0.75
    )
    rows = list(store.db["posting_run_link"].rows)
    assert len(rows) == 1
    assert rows[0]["is_new"] == 1
    assert rows[0]["score"] == 0.75


def test_last_run_for_name_returns_most_recent():
    store = Store(":memory:")
    store.init_schema()
    store.record_run(
        run_id="r1", run_name="x",
        started_at=datetime(2026, 5, 13, 8, 0),
        finished_at=datetime(2026, 5, 13, 8, 5),
        status="ok", config_snapshot={}, summary={}, error=None,
    )
    store.record_run(
        run_id="r2", run_name="x",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok", config_snapshot={}, summary={}, error=None,
    )
    assert store.last_run_for_name("x")["run_id"] == "r2"


def test_last_run_for_unknown_name_returns_none():
    store = Store(":memory:")
    store.init_schema()
    assert store.last_run_for_name("unknown") is None
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_store_runs.py -v
```
Expected: `AttributeError`.

- [ ] **Step 3: Add run + link helpers to `store.py`**

Append to `src/job_identifier/store.py`:
```python
def record_run(
    self,
    run_id: str,
    run_name: str,
    started_at: datetime,
    finished_at: datetime | None,
    status: str,
    config_snapshot: dict,
    summary: dict,
    error: str | None,
) -> None:
    self.db["runs"].insert({
        "run_id": run_id,
        "run_name": run_name,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat() if finished_at else None,
        "status": status,
        "config_snapshot": json.dumps(config_snapshot),
        "summary": json.dumps(summary),
        "error": error,
    }, pk="run_id", replace=True)


def link_posting_to_run(self, run_id: str, posting_id: str, is_new: bool, score: float) -> None:
    self.db["posting_run_link"].insert({
        "run_id": run_id,
        "posting_id": posting_id,
        "is_new": 1 if is_new else 0,
        "score": score,
    }, pk=("run_id", "posting_id"), replace=True)


def last_run_for_name(self, run_name: str) -> dict | None:
    rows = list(self.db.query(
        "SELECT * FROM runs WHERE run_name = ? ORDER BY started_at DESC LIMIT 1",
        [run_name],
    ))
    return rows[0] if rows else None


Store.record_run = record_run
Store.link_posting_to_run = link_posting_to_run
Store.last_run_for_name = last_run_for_name
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_store_runs.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/store.py tests/test_store_runs.py
git commit -m "feat(store): record_run + link_posting_to_run + last_run_for_name"
```

---

### Task 1C.4: Dedupe tagger

**Files:**
- Create: `src/job_identifier/dedupe.py`
- Create: `tests/test_dedupe.py`

- [ ] **Step 1: Write the failing test**

`tests/test_dedupe.py`:
```python
from dataclasses import replace
from datetime import date, datetime
from job_identifier.dedupe import tag_is_new
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.store import Store


def _p(pid: str) -> Posting:
    return Posting(
        posting_id=pid,
        source="s", source_url="u", fetched_at=datetime(2026, 5, 13),
        title="t", company="c", company_normalized="c",
        location="l", country="US", posted_date=date(2026, 5, 1),
        description="d", description_excerpt="",
        skill_matches=[], industry_match=False,
        role_type=RoleType.OTHER, seniority=Seniority.IC,
        recency_score=0.0, seniority_score=0.0, score=0.0, is_new=False,
    )


def test_all_new_when_store_empty():
    store = Store(":memory:")
    store.init_schema()
    tagged = tag_is_new([_p("a"), _p("b")], store)
    assert all(p.is_new for p in tagged)


def test_marks_existing_as_not_new():
    store = Store(":memory:")
    store.init_schema()
    store.upsert_posting(_p("a"), seen_at=datetime(2026, 5, 12))
    tagged = tag_is_new([_p("a"), _p("b")], store)
    by_id = {p.posting_id: p.is_new for p in tagged}
    assert by_id["a"] is False
    assert by_id["b"] is True
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_dedupe.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `dedupe.py`**

```python
from __future__ import annotations
from dataclasses import replace

from job_identifier.models import Posting
from job_identifier.store import Store


def tag_is_new(postings: list[Posting], store: Store) -> list[Posting]:
    return [
        replace(p, is_new=not store.posting_exists(p.posting_id))
        for p in postings
    ]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_dedupe.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/dedupe.py tests/test_dedupe.py
git commit -m "feat(dedupe): tag is_new against Store"
```

---

### Task 1C.5: SQLite sink — atomic write of postings + run + links

**Files:**
- Create: `src/job_identifier/sink/sqlite.py`
- Create: `tests/test_sink_sqlite.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sink_sqlite.py`:
```python
from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority, RunResult
from job_identifier.sink.sqlite import write_run
from job_identifier.store import Store


def _p(pid: str, is_new: bool = True, score: float = 0.5) -> Posting:
    return Posting(
        posting_id=pid,
        source="s", source_url="u", fetched_at=datetime(2026, 5, 13),
        title="t", company="c", company_normalized="c",
        location="l", country="US", posted_date=date(2026, 5, 1),
        description="d", description_excerpt="",
        skill_matches=[], industry_match=False,
        role_type=RoleType.OTHER, seniority=Seniority.IC,
        recency_score=0.0, seniority_score=0.0, score=score,
        is_new=is_new,
    )


def test_write_run_persists_postings_and_links():
    store = Store(":memory:")
    store.init_schema()
    result = RunResult(
        run_id="r1", run_name="x",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok", summary={"total": 2},
    )
    write_run(store, [_p("a"), _p("b", is_new=False, score=0.7)], result, config_snapshot={})
    assert len(list(store.db["postings"].rows)) == 2
    assert len(list(store.db["posting_run_link"].rows)) == 2
    assert store.last_run_for_name("x")["run_id"] == "r1"


def test_write_run_is_idempotent_on_replay():
    store = Store(":memory:")
    store.init_schema()
    result = RunResult(
        run_id="r1", run_name="x",
        started_at=datetime(2026, 5, 13, 10, 0),
        finished_at=datetime(2026, 5, 13, 10, 5),
        status="ok",
    )
    write_run(store, [_p("a")], result, config_snapshot={})
    write_run(store, [_p("a")], result, config_snapshot={})
    assert len(list(store.db["posting_run_link"].rows)) == 1
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_sink_sqlite.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `sink/sqlite.py`**

```python
from __future__ import annotations

from job_identifier.models import Posting, RunResult
from job_identifier.store import Store


def write_run(
    store: Store,
    postings: list[Posting],
    result: RunResult,
    config_snapshot: dict,
) -> None:
    store.record_run(
        run_id=result.run_id,
        run_name=result.run_name,
        started_at=result.started_at,
        finished_at=result.finished_at,
        status=result.status,
        config_snapshot=config_snapshot,
        summary=result.summary,
        error=result.error,
    )
    for p in postings:
        store.upsert_posting(p, seen_at=result.finished_at or result.started_at)
        store.link_posting_to_run(
            run_id=result.run_id,
            posting_id=p.posting_id,
            is_new=p.is_new,
            score=p.score,
        )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sink_sqlite.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/sink/sqlite.py tests/test_sink_sqlite.py
git commit -m "feat(sink/sqlite): atomic write of postings + run + links"
```

---

## Phase 1D — Enrich (Firecrawl)

**Owns:** `enrich/firecrawl_jd.py`, `tests/test_enrich.py`.
**Depends on:** `models` only. Per spec section 6.4, enrich does NOT re-filter; that's the runner's job.

---

### Task 1D.1: Enrich short JDs via Firecrawl

**Files:**
- Create: `src/job_identifier/enrich/firecrawl_jd.py`
- Create: `tests/test_enrich.py`

- [ ] **Step 1: Write the failing test**

`tests/test_enrich.py`:
```python
from dataclasses import replace
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
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_enrich.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `enrich/firecrawl_jd.py`**

```python
from __future__ import annotations
import logging
from dataclasses import replace
from typing import Protocol

from job_identifier.models import Posting

log = logging.getLogger(__name__)


class FirecrawlClientProtocol(Protocol):
    def scrape_url(self, url: str) -> dict:
        ...


def fill_short_descriptions(
    postings: list[Posting],
    min_chars: int,
    client: FirecrawlClientProtocol,
) -> list[Posting]:
    out: list[Posting] = []
    for p in postings:
        if len(p.description) >= min_chars:
            out.append(p)
            continue
        try:
            result = client.scrape_url(p.source_url)
            longer = result.get("markdown") or result.get("content") or ""
            if len(longer) > len(p.description):
                out.append(replace(p, description=longer))
                continue
        except Exception as e:
            log.warning("Firecrawl failed for %s: %s", p.source_url, e)
        out.append(p)
    return out
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_enrich.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/enrich/firecrawl_jd.py tests/test_enrich.py
git commit -m "feat(enrich): refill short JDs via Firecrawl with safe fallback"
```

---

## Phase 1E — Google Sheets sink

**Owns:** `sink/sheets.py`, `tests/test_sink_sheets.py`.
**Depends on:** `models`, `config`. Uses a mocked `gspread` workbook protocol in tests.

---

### Task 1E.1: Aggregate Companies rows from Postings

**Files:**
- Create: `src/job_identifier/sink/sheets.py`
- Create: `tests/test_sheets_aggregate.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sheets_aggregate.py`:
```python
from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.sink.sheets import aggregate_companies


def _p(company: str, score: float, seniority: Seniority, role_type: RoleType,
       skill_matches: list[str], country: str, posted: date,
       url: str = "https://x.com") -> Posting:
    return Posting(
        posting_id=f"{company}-{posted}",
        source="s", source_url=url, fetched_at=datetime(2026, 5, 13),
        title="t", company=company, company_normalized=company.lower(),
        location="l", country=country, posted_date=posted,
        description="d", description_excerpt="",
        skill_matches=skill_matches, industry_match=True,
        role_type=role_type, seniority=seniority,
        recency_score=0.0, seniority_score=0.0, score=score, is_new=False,
    )


def test_aggregate_groups_by_company_normalized():
    postings = [
        _p("Acme", 0.5, Seniority.IC, RoleType.ENGINEERING, ["Foundry"], "US", date(2026, 5, 1)),
        _p("Acme", 0.8, Seniority.DIRECTOR, RoleType.LEADERSHIP, ["AIP"], "US", date(2026, 5, 10)),
        _p("Beta", 0.6, Seniority.SENIOR_IC, RoleType.DATA_AI, ["Foundry"], "GB", date(2026, 5, 5)),
    ]
    rows = aggregate_companies(postings)
    assert len(rows) == 2
    acme = next(r for r in rows if r["company"] == "Acme")
    assert acme["score"] == 0.8
    assert acme["open_roles"] == 2
    assert acme["most_recent_posting"] == "2026-05-10"
    assert acme["most_senior_role"] == "DIRECTOR"
    assert set(acme["role_type_mix"].split(", ")) == {"ENGINEERING", "LEADERSHIP"}
    assert set(acme["skill_matches"].split(", ")) == {"Foundry", "AIP"}
    assert acme["country"] == "US"
    assert "Acme" in acme["linkedin_company_search"]
    assert acme["relationship_status"] == "new prospect"


def test_aggregate_sorts_by_score_desc():
    postings = [
        _p("Low", 0.3, Seniority.IC, RoleType.ENGINEERING, ["Foundry"], "US", date(2026, 5, 1)),
        _p("High", 0.9, Seniority.DIRECTOR, RoleType.LEADERSHIP, ["AIP"], "US", date(2026, 5, 10)),
    ]
    rows = aggregate_companies(postings)
    assert rows[0]["company"] == "High"
    assert rows[1]["company"] == "Low"
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_sheets_aggregate.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement aggregation in `sink/sheets.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sheets_aggregate.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/sink/sheets.py tests/test_sheets_aggregate.py
git commit -m "feat(sink/sheets): aggregate postings into Companies rows"
```

---

### Task 1E.2: Postings rows + edit-preservation logic

**Files:**
- Modify: `src/job_identifier/sink/sheets.py`
- Create: `tests/test_sheets_postings.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sheets_postings.py`:
```python
from datetime import date, datetime
from job_identifier.models import Posting, RoleType, Seniority
from job_identifier.sink.sheets import build_postings_rows, merge_preserved_edits


def _p(pid: str, score: float = 0.5) -> Posting:
    return Posting(
        posting_id=pid, source="s", source_url=f"https://x.com/{pid}",
        fetched_at=datetime(2026, 5, 13),
        title="Senior Foundry Engineer", company="Acme", company_normalized="acme",
        location="NYC", country="US", posted_date=date(2026, 5, 10),
        description="d", description_excerpt="...Foundry...",
        skill_matches=["Foundry"], industry_match=True,
        role_type=RoleType.ENGINEERING, seniority=Seniority.SENIOR_IC,
        recency_score=0.96, seniority_score=0.40, score=score, is_new=True,
    )


def test_build_postings_rows_sorted_by_score():
    rows = build_postings_rows([_p("a", 0.3), _p("b", 0.9)])
    assert rows[0]["posting_id"] == "b"
    assert rows[1]["posting_id"] == "a"
    assert rows[0]["is_new"] == "NEW"


def test_merge_preserved_edits_keys_by_posting_id():
    new = [{"posting_id": "a", "assigned_to": "", "notes": "", "company": "X", "title": "T"}]
    existing = [{"posting_id": "a", "assigned_to": "alice", "notes": "follow up"}]
    merged, archived = merge_preserved_edits(
        new_rows=new, existing_rows=existing, key_field="posting_id"
    )
    assert merged[0]["assigned_to"] == "alice"
    assert merged[0]["notes"] == "follow up"
    assert archived == []


def test_merge_archives_lost_edits():
    new: list[dict] = []
    existing = [{"posting_id": "gone", "assigned_to": "alice", "notes": "n"}]
    merged, archived = merge_preserved_edits(
        new_rows=new, existing_rows=existing, key_field="posting_id"
    )
    assert len(archived) == 1
    assert archived[0]["posting_id"] == "gone"


def test_merge_does_not_archive_empty_existing():
    new: list[dict] = []
    existing = [{"posting_id": "gone", "assigned_to": "", "notes": ""}]
    merged, archived = merge_preserved_edits(
        new_rows=new, existing_rows=existing, key_field="posting_id"
    )
    assert archived == []
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_sheets_postings.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Add to `sink/sheets.py`**

Append:
```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sheets_postings.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/sink/sheets.py tests/test_sheets_postings.py
git commit -m "feat(sink/sheets): build Postings rows + edit-preservation merge"
```

---

### Task 1E.3: `write_sheets()` orchestrator + workbook protocol

**Files:**
- Modify: `src/job_identifier/sink/sheets.py`
- Create: `tests/test_sheets_write.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sheets_write.py`:
```python
from datetime import date, datetime
from unittest.mock import MagicMock
from job_identifier.models import (
    OutputConfig, Posting, RoleType, Seniority,
)
from job_identifier.sink.sheets import write_sheets


def _p(pid: str, score: float = 0.5) -> Posting:
    return Posting(
        posting_id=pid, source="s", source_url=f"https://x.com/{pid}",
        fetched_at=datetime(2026, 5, 13),
        title="Foundry Engineer", company="Acme", company_normalized="acme",
        location="NYC", country="US", posted_date=date(2026, 5, 10),
        description="d", description_excerpt="...Foundry...",
        skill_matches=["Foundry"], industry_match=True,
        role_type=RoleType.ENGINEERING, seniority=Seniority.IC,
        recency_score=0.0, seniority_score=0.0, score=score, is_new=True,
    )


def test_write_sheets_calls_clear_and_update():
    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = []
    workbook.postings_tab.read_rows.return_value = []

    output = OutputConfig(
        companies_tab="Companies", postings_tab="Postings", archived_tab="Archived",
    )
    write_sheets(workbook=workbook, postings=[_p("a")], output_config=output)

    workbook.companies_tab.clear.assert_called_once()
    workbook.companies_tab.write_rows.assert_called_once()
    workbook.postings_tab.clear.assert_called_once()
    workbook.postings_tab.write_rows.assert_called_once()


def test_write_sheets_preserves_edits():
    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = [
        {"company": "Acme", "assigned_to": "alice", "notes": "ping"}
    ]
    workbook.postings_tab.read_rows.return_value = []

    output = OutputConfig(
        companies_tab="Companies", postings_tab="Postings", archived_tab="Archived",
    )
    write_sheets(workbook=workbook, postings=[_p("a")], output_config=output)

    written = workbook.companies_tab.write_rows.call_args.args[0]
    assert written[0]["assigned_to"] == "alice"
    assert written[0]["notes"] == "ping"


def test_write_sheets_archives_orphan_edits():
    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = [
        {"company": "Gone", "assigned_to": "alice", "notes": "n"}
    ]
    workbook.postings_tab.read_rows.return_value = []

    output = OutputConfig(
        companies_tab="Companies", postings_tab="Postings", archived_tab="Archived",
    )
    write_sheets(workbook=workbook, postings=[_p("a")], output_config=output)

    workbook.archived_tab.append_rows.assert_called_once()
    appended = workbook.archived_tab.append_rows.call_args.args[0]
    assert any(r["company"] == "Gone" for r in appended)
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_sheets_write.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Add `write_sheets` and workbook protocol to `sink/sheets.py`**

```python
from typing import Protocol


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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sheets_write.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/sink/sheets.py tests/test_sheets_write.py
git commit -m "feat(sink/sheets): write_sheets orchestrator with edit preservation"
```

---

### Task 1E.4: gspread-backed Workbook implementation

**Files:**
- Modify: `src/job_identifier/sink/sheets.py`

- [ ] **Step 1: Add concrete gspread-backed implementation**

Append to `src/job_identifier/sink/sheets.py`:
```python
import gspread
from google.oauth2.service_account import Credentials

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class _GspreadTab:
    def __init__(self, worksheet):
        self._ws = worksheet

    def read_rows(self) -> list[dict]:
        try:
            return self._ws.get_all_records()
        except Exception:
            return []

    def clear(self) -> None:
        self._ws.clear()

    def write_rows(self, rows: list[dict]) -> None:
        if not rows:
            return
        headers = list(rows[0].keys())
        values = [headers] + [[r.get(h, "") for h in headers] for r in rows]
        self._ws.update("A1", values)

    def append_rows(self, rows: list[dict]) -> None:
        if not rows:
            return
        existing = self.read_rows()
        all_rows = existing + rows
        self.clear()
        self.write_rows(all_rows)


class GspreadWorkbook:
    """Concrete Workbook implementation backed by gspread."""

    def __init__(self, workbook_id: str, creds_path: str, output_config):
        creds = Credentials.from_service_account_file(creds_path, scopes=_SCOPES)
        client = gspread.authorize(creds)
        self._sh = client.open_by_key(workbook_id)
        self._output = output_config

    def _get_or_create_tab(self, title: str) -> _GspreadTab:
        try:
            ws = self._sh.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self._sh.add_worksheet(title=title, rows=1000, cols=26)
        return _GspreadTab(ws)

    @property
    def companies_tab(self) -> _GspreadTab:
        return self._get_or_create_tab(self._output.companies_tab)

    @property
    def postings_tab(self) -> _GspreadTab:
        return self._get_or_create_tab(self._output.postings_tab)

    @property
    def archived_tab(self) -> _GspreadTab:
        return self._get_or_create_tab(self._output.archived_tab)
```

- [ ] **Step 2: Verify the existing test suite still passes**

```bash
pytest tests/test_sheets_write.py tests/test_sheets_aggregate.py tests/test_sheets_postings.py -v
```
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add src/job_identifier/sink/sheets.py
git commit -m "feat(sink/sheets): add gspread-backed Workbook implementation"
```

(No live-API test at MVP — verified manually in Phase 4.)

---

**Phase 1 exit criteria:**
- All workstream tests pass: `pytest tests/ -v`
- Modules are importable: `python -c "from job_identifier import sources, sink, enrich; from job_identifier import filter, score, dedupe, store, normalize"`

After Phase 1 merges into main, Phase 2 (integration) begins.

---

## Phase 2 — Integration: runner + CLI

**Owns:** `runner.py`, `cli.py`, `tests/test_runner.py`, `tests/test_cli.py`.

---

### Task 2.1: Runner — happy path composition

**Files:**
- Create: `src/job_identifier/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

`tests/test_runner.py`:
```python
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from job_identifier.config import load_runs
from job_identifier.runner import run
from job_identifier.store import Store


def test_runner_happy_path(raw_serpapi_response, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "job_identifier.runner.fetch_jobs",
        lambda cfg, api_key: [raw_serpapi_response],
    )

    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = []
    workbook.postings_tab.read_rows.return_value = []
    monkeypatch.setattr(
        "job_identifier.runner.open_workbook",
        lambda run_name, secrets, output_config: workbook,
    )

    monkeypatch.setattr(
        "job_identifier.runner.firecrawl_client",
        lambda secrets: MagicMock(scrape_url=MagicMock(return_value={"markdown": ""})),
    )

    store = Store(str(tmp_path / "test.db"))
    store.init_schema()

    runs = load_runs(Path("config/runs.yaml"))
    secrets = MagicMock(serpapi_key="x", firecrawl_api_key="x")

    result = run(
        run_config=runs[0],
        secrets=secrets,
        store=store,
        now=datetime(2026, 5, 13, 10, 0, 0),
    )

    assert result.status == "ok"
    assert result.summary["fetched"] >= 1
    assert result.summary["filtered"] >= 1
    assert result.summary["scored"] == result.summary["filtered"]
    workbook.companies_tab.write_rows.assert_called_once()


def test_runner_dry_run_skips_sinks(raw_serpapi_response, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "job_identifier.runner.fetch_jobs",
        lambda cfg, api_key: [raw_serpapi_response],
    )
    workbook = MagicMock()
    monkeypatch.setattr(
        "job_identifier.runner.open_workbook",
        lambda run_name, secrets, output_config: workbook,
    )
    monkeypatch.setattr(
        "job_identifier.runner.firecrawl_client",
        lambda secrets: MagicMock(scrape_url=MagicMock(return_value={"markdown": ""})),
    )

    store = Store(str(tmp_path / "test.db"))
    store.init_schema()

    runs = load_runs(Path("config/runs.yaml"))
    result = run(
        run_config=runs[0],
        secrets=MagicMock(),
        store=store,
        now=datetime(2026, 5, 13),
        dry_run=True,
    )

    assert result.status == "ok"
    workbook.companies_tab.write_rows.assert_not_called()
    assert len(list(store.db["runs"].rows)) == 0
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_runner.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `runner.py`**

```python
from __future__ import annotations
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any

from ulid import ULID

from job_identifier import filter as filter_module
from job_identifier import score as score_module
from job_identifier.dedupe import tag_is_new
from job_identifier.enrich.firecrawl_jd import fill_short_descriptions
from job_identifier.models import RunConfig, RunResult, Secrets
from job_identifier.normalize import normalize_serpapi_jobs
from job_identifier.sink.sheets import GspreadWorkbook, write_sheets
from job_identifier.sink.sqlite import write_run
from job_identifier.sources.serpapi_jobs import fetch_jobs
from job_identifier.store import Store

log = logging.getLogger(__name__)


def firecrawl_client(secrets: Secrets):
    from firecrawl import FirecrawlApp
    return FirecrawlApp(api_key=secrets.firecrawl_api_key)


def open_workbook(run_name: str, secrets: Secrets, output_config) -> GspreadWorkbook:
    workbook_id = secrets.workbook_ids_by_run[run_name]
    return GspreadWorkbook(
        workbook_id=workbook_id,
        creds_path=secrets.google_sheets_creds_path,
        output_config=output_config,
    )


def run(
    run_config: RunConfig,
    secrets: Secrets,
    store: Store,
    now: datetime,
    dry_run: bool = False,
) -> RunResult:
    run_id = str(ULID())
    summary: dict[str, Any] = {}
    result = RunResult(
        run_id=run_id,
        run_name=run_config.name,
        started_at=now,
        finished_at=None,
        status="running",
        summary=summary,
    )

    try:
        responses = fetch_jobs(run_config, api_key=secrets.serpapi_key)
        raw_count = sum(len(r.get("jobs_results", [])) for r in responses)
        summary["fetched"] = raw_count

        all_postings = []
        for resp in responses:
            all_postings.extend(normalize_serpapi_jobs(resp, fetched_at=now))
        summary["normalized"] = len(all_postings)

        filtered = filter_module.apply(all_postings, run_config, now=now)
        summary["filtered_first_pass"] = len(filtered)

        if not dry_run:
            client = firecrawl_client(secrets)
            enriched = fill_short_descriptions(
                filtered,
                min_chars=run_config.enrichment.firecrawl_min_jd_chars,
                client=client,
            )
        else:
            enriched = filtered

        # Re-filter the enriched subset only (spec §6.4).
        changed_ids = {
            p.posting_id for p, e in zip(filtered, enriched) if p.description != e.description
        }
        rest = [p for p in enriched if p.posting_id not in changed_ids]
        rechecked = filter_module.apply(
            [p for p in enriched if p.posting_id in changed_ids],
            run_config,
            now=now,
        )
        filtered_after = rest + rechecked
        summary["filtered"] = len(filtered_after)

        tagged = tag_is_new(filtered_after, store)
        summary["new"] = sum(1 for p in tagged if p.is_new)

        scored = score_module.apply(tagged, run_config, now=now)
        summary["scored"] = len(scored)

        result.finished_at = datetime.now()
        result.status = "ok"
        result.summary = summary

        if dry_run:
            log.info("Dry run complete, skipping sinks")
            return result

        write_run(
            store=store,
            postings=scored,
            result=result,
            config_snapshot=_config_snapshot(run_config),
        )

        try:
            workbook = open_workbook(run_config.name, secrets, run_config.output)
            write_sheets(
                workbook=workbook,
                postings=scored,
                output_config=run_config.output,
            )
        except Exception as e:
            log.exception("Sheet write failed")
            result.status = "sheet_write_failed"
            result.error = str(e)
            store.record_run(
                run_id=result.run_id, run_name=result.run_name,
                started_at=result.started_at, finished_at=result.finished_at,
                status=result.status, config_snapshot=_config_snapshot(run_config),
                summary=result.summary, error=result.error,
            )

        return result

    except Exception as e:
        log.exception("Run failed")
        result.status = "failed"
        result.error = str(e)
        result.finished_at = datetime.now()
        if not dry_run:
            store.record_run(
                run_id=result.run_id, run_name=result.run_name,
                started_at=result.started_at, finished_at=result.finished_at,
                status="failed", config_snapshot=_config_snapshot(run_config),
                summary=summary, error=str(e),
            )
        return result


def _config_snapshot(cfg: RunConfig) -> dict:
    """Convert RunConfig to a plain-dict snapshot for storage."""
    return {
        "name": cfg.name,
        "enabled": cfg.enabled,
        "skill": asdict(cfg.skill),
        "industry": asdict(cfg.industry),
        "geos": cfg.geos,
        "recency_window_days": cfg.recency_window_days,
        "score_weights": asdict(cfg.score_weights),
        "enrichment": asdict(cfg.enrichment),
        "output": asdict(cfg.output),
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_runner.py -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/job_identifier/runner.py tests/test_runner.py
git commit -m "feat(runner): compose pipeline stages, handle error matrix"
```

---

### Task 2.2: CLI

**Files:**
- Create: `src/job_identifier/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
from pathlib import Path
from typer.testing import CliRunner
from job_identifier.cli import app


def test_list_runs_outputs_names():
    runner = CliRunner()
    config_path = Path(__file__).parent.parent / "config" / "runs.yaml"
    result = runner.invoke(app, ["list-runs", "--config", str(config_path)])
    assert result.exit_code == 0
    assert "palantir_insurance" in result.stdout
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_cli.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `cli.py`**

```python
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

import typer

from job_identifier.config import load_runs, load_secrets
from job_identifier.runner import run as run_pipeline
from job_identifier.store import Store

app = typer.Typer(help="Job Identifier CLI")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@app.command("list-runs")
def list_runs(
    config: Path = typer.Option(Path("config/runs.yaml"), "--config", "-c"),
):
    runs = load_runs(config)
    for r in runs:
        marker = "✓" if r.enabled else "✗"
        typer.echo(f"  {marker} {r.name}  ({len(r.geos)} geos, {len(r.skill.query_terms)} queries)")


@app.command("run")
def run_cmd(
    name: str = typer.Argument(..., help="Run name from config"),
    config: Path = typer.Option(Path("config/runs.yaml"), "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    db: Path = typer.Option(Path("data/jobs.db"), "--db"),
):
    runs = load_runs(config)
    selected = next((r for r in runs if r.name == name), None)
    if selected is None:
        typer.echo(f"No run named {name!r}", err=True)
        raise typer.Exit(code=1)

    secrets = load_secrets(run_names=[name])
    store = Store(str(db))
    store.init_schema()

    result = run_pipeline(
        run_config=selected,
        secrets=secrets,
        store=store,
        now=datetime.now(),
        dry_run=dry_run,
    )
    typer.echo(f"\nRun {result.run_id}: status={result.status}")
    for k, v in result.summary.items():
        typer.echo(f"  {k}: {v}")
    if result.error:
        typer.echo(f"  error: {result.error}", err=True)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cli.py -v
```
Expected: pass.

- [ ] **Step 5: Verify the command line entry point**

```bash
job-id list-runs
```
Expected: prints `✓ palantir_insurance (5 geos, 3 queries)`.

- [ ] **Step 6: Commit**

```bash
git add src/job_identifier/cli.py tests/test_cli.py
git commit -m "feat(cli): list-runs and run commands via typer"
```

---

### Task 2.3: Per-run JSON log files

Spec §11 requires structured JSON logging to `data/logs/<run_id>.log`. The Streamlit Run detail page tails the latest log file (added in Task 3.2 below).

**Files:**
- Create: `src/job_identifier/logging_setup.py`
- Modify: `src/job_identifier/runner.py`
- Create: `tests/test_logging_setup.py`

- [ ] **Step 1: Write the failing test**

`tests/test_logging_setup.py`:
```python
import json
import logging
from pathlib import Path
from job_identifier.logging_setup import setup_run_logger


def test_setup_run_logger_writes_json_to_file(tmp_path):
    log_dir = tmp_path / "logs"
    logger, handler = setup_run_logger("run_abc", log_dir=log_dir)
    logger.info("hello", extra={"stage": "test"})
    handler.flush()
    log_file = log_dir / "run_abc.log"
    assert log_file.exists()
    line = log_file.read_text().strip().split("\n")[0]
    parsed = json.loads(line)
    assert parsed["message"] == "hello"
    assert parsed["stage"] == "test"
    logger.removeHandler(handler)
    handler.close()
```

- [ ] **Step 2: Run test and verify it fails**

```bash
pytest tests/test_logging_setup.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `logging_setup.py`**

```python
from __future__ import annotations
import json
import logging
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Promote any extra attributes
        for k, v in record.__dict__.items():
            if k in {"args", "msg", "name", "levelname", "levelno", "pathname",
                     "filename", "module", "exc_info", "exc_text", "stack_info",
                     "lineno", "funcName", "created", "msecs", "relativeCreated",
                     "thread", "threadName", "processName", "process",
                     "taskName", "message", "asctime"}:
                continue
            payload[k] = v
        return json.dumps(payload)


def setup_run_logger(run_id: str, log_dir: Path) -> tuple[logging.Logger, logging.Handler]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{run_id}.log"
    handler = logging.FileHandler(log_file)
    handler.setFormatter(_JsonFormatter())
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("job_identifier")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger, handler
```

- [ ] **Step 4: Wire it into the runner**

In `src/job_identifier/runner.py`, at the top of `run()`:
```python
from pathlib import Path
from job_identifier.logging_setup import setup_run_logger
```

Then at the start of `run()`, after `run_id = str(ULID())`:
```python
log_dir = Path("data/logs")
file_logger, handler = setup_run_logger(run_id, log_dir)
```

And in a `finally` block wrapping the existing try/except in `run()`:
```python
try:
    # ... existing body ...
finally:
    handler.flush()
    file_logger.removeHandler(handler)
    handler.close()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_logging_setup.py tests/test_runner.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/job_identifier/logging_setup.py src/job_identifier/runner.py tests/test_logging_setup.py
git commit -m "feat(logging): JSON-formatted per-run log files in data/logs/"
```

---

## Phase 3 — Streamlit UI

**Owns:** `app.py`, `ui/pages/`, `ui/components/`.
**Depends on:** Phase 2's `runner`, Phase 1-C's `store`. Can begin during Phase 2.

---

### Task 3.1: Streamlit entry + Runs landing page

**Files:**
- Create: `src/job_identifier/ui/app.py`
- Create: `src/job_identifier/ui/pages/01_Runs.py`

- [ ] **Step 1: Implement `ui/app.py`**

```python
import streamlit as st

st.set_page_config(page_title="Job Identifier", layout="wide")
st.title("Job Identifier")
st.write("Select a page from the sidebar.")
```

- [ ] **Step 2: Implement `ui/pages/01_Runs.py`**

```python
from datetime import datetime
from pathlib import Path
import json
import streamlit as st

from job_identifier.config import load_runs, load_secrets
from job_identifier.runner import run as run_pipeline
from job_identifier.store import Store

CONFIG_PATH = Path("config/runs.yaml")
DB_PATH = Path("data/jobs.db")

st.title("Runs")

runs = load_runs(CONFIG_PATH)
store = Store(str(DB_PATH))
store.init_schema()

rows = []
for r in runs:
    last = store.last_run_for_name(r.name)
    if last:
        summary = json.loads(last["summary"]) if last.get("summary") else {}
        rows.append({
            "Run": r.name,
            "Last run": last["started_at"][:19],
            "Status": last["status"],
            "New": summary.get("new", "—"),
            "Total": summary.get("scored", "—"),
        })
    else:
        rows.append({
            "Run": r.name,
            "Last run": "never",
            "Status": "—",
            "New": "—",
            "Total": "—",
        })

st.dataframe(rows, use_container_width=True)

st.divider()
st.subheader("Trigger a run")
choice = st.selectbox("Run to execute", [r.name for r in runs if r.enabled])
dry = st.checkbox("Dry run (no Sheet write)", value=False)
if st.button("Run now", type="primary"):
    selected = next(r for r in runs if r.name == choice)
    try:
        secrets = load_secrets(run_names=[choice])
    except RuntimeError as e:
        st.error(f"Missing secret: {e}")
        st.stop()
    with st.status(f"Running {choice}...", expanded=True) as status:
        result = run_pipeline(
            run_config=selected, secrets=secrets, store=store,
            now=datetime.now(), dry_run=dry,
        )
        for k, v in result.summary.items():
            st.write(f"**{k}**: {v}")
        if result.status == "ok":
            status.update(label=f"Done ✓ ({result.status})", state="complete")
        else:
            status.update(label=f"Failed: {result.status}", state="error")
            if result.error:
                st.error(result.error)
```

- [ ] **Step 3: Verify the UI starts**

```bash
streamlit run src/job_identifier/ui/app.py
```
Expected: opens browser to localhost:8501, shows "Runs" in sidebar.

- [ ] **Step 4: Commit**

```bash
git add src/job_identifier/ui/app.py src/job_identifier/ui/pages/01_Runs.py
git commit -m "feat(ui): Streamlit entry + Runs landing page"
```

---

### Task 3.2: Run detail page

**Files:**
- Create: `src/job_identifier/ui/pages/02_Run_detail.py`

- [ ] **Step 1: Implement the page**

```python
from pathlib import Path
import json
import streamlit as st

from job_identifier.config import load_runs
from job_identifier.store import Store

CONFIG_PATH = Path("config/runs.yaml")
DB_PATH = Path("data/jobs.db")

st.title("Run detail")

runs = load_runs(CONFIG_PATH)
store = Store(str(DB_PATH))
store.init_schema()

selected = st.selectbox("Run", [r.name for r in runs])
cfg = next(r for r in runs if r.name == selected)

with st.expander("Current config (from runs.yaml)"):
    st.code(str(cfg), language="python")

last_runs = list(store.db.query(
    "SELECT * FROM runs WHERE run_name = ? ORDER BY started_at DESC LIMIT 10",
    [selected],
))
if not last_runs:
    st.info("No runs yet. Trigger one from the Runs page.")
    st.stop()

st.subheader("History")
history_rows = []
for r in last_runs:
    summary = json.loads(r["summary"]) if r.get("summary") else {}
    history_rows.append({
        "Started": r["started_at"][:19],
        "Status": r["status"],
        "Filtered": summary.get("filtered", "—"),
        "New": summary.get("new", "—"),
        "Scored": summary.get("scored", "—"),
    })
st.dataframe(history_rows, use_container_width=True)

st.subheader("What's new since last run (top 10)")
latest = last_runs[0]
new_postings = list(store.db.query("""
    SELECT json_extract(p.payload, '$.company') AS company,
           json_extract(p.payload, '$.title') AS title,
           json_extract(p.payload, '$.country') AS country,
           json_extract(p.payload, '$.seniority') AS seniority,
           l.score AS score,
           json_extract(p.payload, '$.source_url') AS source_url
    FROM posting_run_link l
    JOIN postings p ON p.posting_id = l.posting_id
    WHERE l.run_id = ? AND l.is_new = 1
    ORDER BY l.score DESC
    LIMIT 10
""", [latest["run_id"]]))
if new_postings:
    st.dataframe(new_postings, use_container_width=True)
else:
    st.write("No new postings in the most recent run.")

st.subheader("Last run log")
log_file = Path("data/logs") / f"{latest['run_id']}.log"
if log_file.exists():
    with st.expander("Show JSON log", expanded=False):
        st.code(log_file.read_text(), language="json")
else:
    st.caption("No log file for this run.")
```

- [ ] **Step 2: Verify the page renders**

Visit the page in the sidebar.

- [ ] **Step 3: Commit**

```bash
git add src/job_identifier/ui/pages/02_Run_detail.py
git commit -m "feat(ui): run-detail page with history + diff"
```

---

### Task 3.3: Browse page

**Files:**
- Create: `src/job_identifier/ui/pages/03_Browse.py`

- [ ] **Step 1: Implement the page**

```python
from pathlib import Path
import json
import streamlit as st

from job_identifier.store import Store

DB_PATH = Path("data/jobs.db")

st.title("Browse postings")

store = Store(str(DB_PATH))
store.init_schema()

all_postings = list(store.db.query("""
    SELECT p.posting_id AS posting_id,
           json_extract(p.payload, '$.company') AS company,
           json_extract(p.payload, '$.title') AS title,
           json_extract(p.payload, '$.country') AS country,
           json_extract(p.payload, '$.role_type') AS role_type,
           json_extract(p.payload, '$.seniority') AS seniority,
           json_extract(p.payload, '$.posted_date') AS posted_date,
           json_extract(p.payload, '$.score') AS score,
           json_extract(p.payload, '$.source_url') AS source_url
    FROM postings p
"""))

if not all_postings:
    st.info("No postings yet. Trigger a run from the Runs page.")
    st.stop()

countries = sorted({p["country"] for p in all_postings if p.get("country")})
role_types = sorted({p["role_type"] for p in all_postings if p.get("role_type")})
seniorities = sorted({p["seniority"] for p in all_postings if p.get("seniority")})

with st.sidebar:
    st.header("Filters")
    selected_countries = st.multiselect("Country", countries, default=countries)
    selected_role_types = st.multiselect("Role type", role_types, default=role_types)
    selected_seniorities = st.multiselect("Seniority", seniorities, default=seniorities)
    min_score, max_score = st.slider("Score range", 0.0, 1.0, (0.0, 1.0), 0.05)

filtered = [
    p for p in all_postings
    if p["country"] in selected_countries
    and p["role_type"] in selected_role_types
    and p["seniority"] in selected_seniorities
    and min_score <= float(p["score"] or 0) <= max_score
]
filtered.sort(key=lambda p: float(p["score"] or 0), reverse=True)
st.dataframe(filtered, use_container_width=True)
```

- [ ] **Step 2: Verify the page renders**

Visit Browse in the sidebar, confirm filters work.

- [ ] **Step 3: Commit**

```bash
git add src/job_identifier/ui/pages/03_Browse.py
git commit -m "feat(ui): browse page with filterable postings dataframe"
```

---

## Phase 4 — Live signal test + sign-off

### Task 4.1: Live SerpAPI sanity run

- [ ] **Step 1: Set up secrets**

```bash
cp .env.example .env
# Edit .env with real SERPAPI_KEY, FIRECRAWL_API_KEY, GOOGLE_SHEETS_CREDS_PATH
# Create a Google Sheet manually, share it with the service-account email
# Set GSHEET_WORKBOOK_PALANTIR_INSURANCE to the workbook ID from the URL
```

- [ ] **Step 2: Run dry-run first**

```bash
job-id run palantir_insurance --dry-run
```
Expected: prints a summary with `fetched`, `filtered`, `scored` counts. No DB or Sheet writes.

- [ ] **Step 3: Run for real**

```bash
job-id run palantir_insurance
```
Expected: status `ok`, postings persisted, Sheet workbook updated with Companies + Postings tabs.

- [ ] **Step 4: Compare against `docs/test-queries.md` baseline**

Open the Sheet. Spot check ≥5 rows in Companies tab against the criteria from `docs/test-queries.md` Decision rules:
- ≥10 plausible across all geos? → MVP is viable.
- 3-9? → tune `runs.yaml` (expand skill terms, drop quoted phrase).
- <3? → escalate to backlog discussion (carrier ATS crawl via Firecrawl as primary source).

- [ ] **Step 5: Tune YAML if needed**

If signal quality is off (>50% false-positives or <3 plausible matches), edit `config/runs.yaml`:
- Add/remove keywords in `industry.include_keywords`
- Tighten/loosen `skill.query_terms`
- Add to `industry.deny_companies` for consultancies appearing as false positives

Re-run after each change.

- [ ] **Step 6: Partner walkthrough**

Demo the Sheet + UI to one partner. Capture feedback in a Notion/markdown doc — separate artifact, not part of this plan.

- [ ] **Step 7: Tag v0.1.0**

```bash
git tag v0.1.0 -m "MVP: Palantir × Insurance signal pipeline"
```

---

## Cross-cutting verification

After all phases:

- [ ] `pytest tests/ -v` — every test passes
- [ ] `ruff check src/ tests/` — no lint errors
- [ ] `job-id list-runs` works
- [ ] `job-id run palantir_insurance --dry-run` works
- [ ] `streamlit run src/job_identifier/ui/app.py` opens, all three pages render
- [ ] Live run produces a populated Sheet with the expected tabs
- [ ] Re-running preserves edits in `assigned_to` / `notes` columns
- [ ] Editing a `notes` cell, deleting the row from postings, re-running → edits land in the `Archived` tab
