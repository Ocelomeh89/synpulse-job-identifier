# Job Identifier — Design Spec

**Date:** 2026-05-13
**Owner:** Miguel Graf
**Status:** Draft awaiting user approval

## 1. Problem and goal

Synpulse's consulting business needs warm prospect leads in financial services. Public job postings are a high-quality buying signal: an insurance company posting a "Palantir Foundry Engineer" role is publicly declaring both that they use Palantir and that they're investing now. Aggregating those signals into a partner-readable list converts public data into a sales-trigger pipeline.

**First use case:** insurance companies in US, Canada, Mexico, UK, and Bermuda hiring for Palantir Foundry or AIP.

**Generic from day one:** `skill` and `industry` are config, not code. The same pipeline runs unmodified for Snowflake at retailers, Salesforce at fintechs, etc.

**Non-goals (MVP):**
- Outbound sequencing or CRM push (backlog P5)
- Company enrichment (Apollo/Clearbit/ZoomInfo — backlog P1)
- Scheduled runs (backlog P2)
- Inline editing of partner annotations in the custom UI (Sheet remains the editable surface)
- Multi-tenant / shared hosting with auth (backlog P3)

## 2. Users and workflow

**Users:** Miguel + a small group of Synpulse partners and principals. Self-serve, read-Sheet-fluent, no engineering required to operate.

**Trigger:** manual via the Streamlit UI or the CLI. Per-keyword scheduling is in the P2 backlog.

**Action loop per row:**
1. Partner opens the Google Sheet workbook for a run.
2. Triages on the Companies tab (sorted by score).
3. For hot rows: clicks `linkedin_company_search` helper → finds the right person via their own network → warm outreach.
4. For others: fills `assigned_to` to hand off to whichever Synpulse partner is closest to the account, plus `notes`.
5. Partner edits in the Sheet persist across reruns (preservation logic in `sink/sheets`).

## 3. Output contract: Google Sheet structure

**One workbook per configured run.** E.g., `palantir_insurance` is its own workbook. Workbook IDs are stored as env vars (`GSHEET_WORKBOOK_PALANTIR_INSURANCE`) so URLs stay out of git.

### Tab "Companies" — primary triage, sorted by `score` desc

| Column | Source | Notes |
|---|---|---|
| `company` | aggregated | Raw display name |
| `relationship_status` | `"new prospect"` | Hardcoded at MVP; backlog P1 enriches via cross-reference to Synpulse target list |
| `score` | max of postings' scores | Primary sort |
| `open_roles` | count of postings for this company | Volume signal |
| `most_recent_posting` | max `posted_date` | |
| `most_senior_role` | max `seniority` across postings | E.g., "Director" |
| `role_type_mix` | distinct `role_type` values | E.g., "Engineering, Leadership" |
| `skill_matches` | union of `skill_matches` | "Foundry", "AIP", or "Foundry, AIP" |
| `country` | majority country | |
| `linkedin_company_search` | URL helper | `https://linkedin.com/search/results/companies/?keywords=<urlencoded>` |
| `sample_jd_url` | most recent posting's URL | Drill-in |
| `assigned_to` | blank | **Partner edits, preserved across runs** |
| `notes` | blank | **Partner edits, preserved across runs** |

### Tab "Postings" — detail view, sorted by `score` desc

| Column | Source |
|---|---|
| `company`, `title`, `location`, `country`, `posted_date` | `Posting` fields |
| `role_type`, `seniority` | Sheet drop-down validation applied for filtering |
| `skill_matches` | "Foundry" / "AIP" / "Foundry, AIP" |
| `score`, `recency_score`, `seniority_score` | `score.py` output |
| `description_excerpt` | 200-char snippet around first skill match — quote-ready context |
| `job_url` | Direct posting link |
| `is_new` | "NEW" or blank — first time we've seen this posting in any run |
| `linkedin_company_search` | Same helper as Companies tab |
| `assigned_to`, `notes` | Partner editable, preserved across runs |

### Tab "Archived" — failsafe

Any row that previously had non-empty `assigned_to` or `notes` but no longer matches current filters (e.g., aged out of the 90-day window) is appended here so partner annotations are never silently lost.

## 4. Architecture

### Two long-lived processes, one shared state

```
┌──────────────────────────┐         ┌──────────────────────────┐
│ Streamlit UI (web)       │         │ CLI: `job-id run <name>` │
│ • Trigger runs           │         │ (same code, headless)    │
│ • Browse latest results  │         └────────────┬─────────────┘
│ • Run history view       │                      │
│ • Read-only on results   │                      │
└────────────┬─────────────┘                      │
             │                                    │
             ▼                                    ▼
        ┌─────────────────────────────────────────────┐
        │  Orchestrator (`job_identifier.runner`)     │
        │  Loads runs.yaml, executes one Run end-to-end│
        └────────────┬────────────────────────────────┘
                     │
                     ▼  Pipeline (pure-function stages):
   ┌─────────┐   ┌──────────┐   ┌────────┐   ┌────────┐   ┌─────────┐   ┌───────┐   ┌──────┐
   │ source  │ → │ normalize│ → │ filter │ → │ dedupe │ → │ enrich  │ → │ score │ → │ sink │
   │ serpapi │   │          │   │        │   │        │   │firecrawl│   │       │   │sheets│
   └─────────┘   └──────────┘   └────────┘   └────────┘   └─────────┘   └───────┘   └──────┘
                                                                                       │
                                                                                       ▼
                                                                          ┌─────────────────────────┐
                                                                          │ SQLite (`data/jobs.db`) │
                                                                          │ • postings              │
                                                                          │ • runs                  │
                                                                          │ • posting_run_link      │
                                                                          └─────────────────────────┘
```

### Module responsibilities

Every file ≤ ~200 lines. Each module has one clear purpose.

| Module | Owns | Depends on |
|---|---|---|
| `models.py` | `Posting`, `RoleType`, `Seniority`, `RunConfig`, `RunResult` dataclasses/enums | — |
| `config.py` | Load + validate `runs.yaml` via pydantic; `load_secrets()` from `.env` | `models` |
| `sources/serpapi_jobs.py` | Calls SerpAPI Google Jobs, returns raw `dict[]`. Pagination, retries, rate-limit handling. | `config` |
| `normalize.py` | Raw dict → `Posting`. Field mapping, date parsing, `posting_id` hash, `company_normalized`. | `models` |
| `filter.py` | Hard filters (Foundry/AIP, recency, industry, deny-list) + role_type/seniority classification. Pure function. | `models`, `config` |
| `dedupe.py` | Annotate `is_new` against SQLite. Pure with read-only DB access. | `models`, `store` |
| `enrich/firecrawl_jd.py` | Fallback: refill truncated JDs by scraping `source_url`. Re-runs filter on enriched subset. | `models`, `filter` |
| `score.py` | Compute `recency_score`, `seniority_score`, combined `score`. Pure. | `models`, `config` |
| `store.py` | SQLite schema, queries, transactions. Single source of truth for the schema. | `models` |
| `sink/sqlite.py` | Persist postings + run + link rows. One transaction per run. | `models`, `store` |
| `sink/sheets.py` | Write Companies + Postings tabs, preserve partner edits, append Archived. | `models`, `config` |
| `runner.py` | Compose all stages for one Run. Returns `RunResult`. Handles error matrix. | All of the above |
| `cli.py` | `typer` app: `run`, `list-runs`, `dry-run`, `retry-sheet`. | `runner` |
| `app.py` + `ui/pages/` | Streamlit pages: Runs, Run detail, Browse. Imports `runner.run()` directly. | `runner`, `store` |

### Invariants

- The only cross-stage shape is `Posting`. `Company` aggregations are computed at sink-write time, never stored.
- Every stage's function signature: `(list[Posting], context) -> list[Posting]` (or `-> None` for sinks). Easy to test, easy to insert a stage later.
- Streamlit has no business logic. It calls `runner.run()` or reads `store`.
- All keyword lists (skill regex, industry keywords, deny-list, score weights) live in `runs.yaml`, not in code. Partners can tune without engineering help.

## 5. Data model

### `Posting` (cross-stage shape)

```python
@dataclass(frozen=True)
class Posting:
    # Identity
    posting_id: str               # SHA1(company_normalized|title.lower()|country|posted_date)
    source: str                   # "serpapi"
    source_url: str
    fetched_at: datetime

    # Job
    title: str
    company: str                  # raw from source
    company_normalized: str       # lowercased, suffix-stripped (Inc/Ltd/LLC/S.A./AG/plc/...)
    location: str                 # raw
    country: str                  # ISO-2: US / CA / MX / GB / BM
    posted_date: date
    description: str              # JD body, may be Firecrawl-enriched
    description_excerpt: str      # 200 chars around first skill match

    # Classification (filled by filter.py)
    skill_matches: list[str]      # ["Foundry"] / ["AIP"] / ["Foundry", "AIP"]
    industry_match: bool
    role_type: RoleType           # ENGINEERING | DATA_AI | LEADERSHIP | BUSINESS_OPS | OTHER
    seniority: Seniority          # IC | SENIOR_IC | LEAD | DIRECTOR | VP_PLUS

    # Scoring (filled by score.py)
    recency_score: float
    seniority_score: float
    score: float                  # primary sort key

    # Dedupe (filled by dedupe.py)
    is_new: bool                  # True if first time seen across all runs
```

### SQLite schema

```sql
CREATE TABLE postings (
  posting_id        TEXT PRIMARY KEY,
  payload           TEXT NOT NULL,        -- full Posting as JSON; schema-less for safety
  first_seen_at     TEXT NOT NULL,
  last_seen_at      TEXT NOT NULL
);

CREATE TABLE runs (
  run_id            TEXT PRIMARY KEY,     -- ulid
  run_name          TEXT NOT NULL,        -- "palantir_insurance"
  started_at        TEXT NOT NULL,
  finished_at       TEXT,
  status            TEXT NOT NULL,        -- running | ok | failed | sheet_write_failed
  config_snapshot   TEXT NOT NULL,        -- runs.yaml entry at run time, JSON
  summary           TEXT,                 -- per-stage counts, JSON
  error             TEXT
);

CREATE TABLE posting_run_link (
  run_id            TEXT NOT NULL,
  posting_id        TEXT NOT NULL,
  is_new            INTEGER NOT NULL,
  score             REAL,
  PRIMARY KEY (run_id, posting_id)
);

CREATE INDEX idx_runs_name_started ON runs(run_name, started_at DESC);
CREATE INDEX idx_link_run ON posting_run_link(run_id);
```

JSON-payload for postings means we don't fight schema migrations as `Posting` evolves. `runs.config_snapshot` means we can replay an old run's logic.

## 6. Pipeline stages

### Stage order

```
1. source.fetch()       → list[dict]
2. normalize()          → list[Posting]
3. filter.apply()       → list[Posting]   (hard-filtered + classified)
4. enrich.fill()        → list[Posting]   (refills truncated JDs, count unchanged)
4b. filter.apply()      → list[Posting]   (re-run on enriched subset only; runner does this)
5. dedupe.tag()         → list[Posting]   (is_new annotated)
6. score.compute()      → list[Posting]   (recency, seniority, combined)
7. sink.write_sqlite()  → None
8. sink.write_sheets()  → None
```

### 1. `sources/serpapi_jobs.fetch(run_config) → list[dict]`

- One SerpAPI Google Jobs call per `(geo × skill query_term)` combination. Example: 5 geos × 3 query_terms = 15 calls.
- Paginates via `next_page_token` until empty or 5 pages, whichever first.
- Retries: 3 attempts with exponential backoff (1s, 4s, 9s) on 5xx and transient errors. Hard failure on 4xx.
- Logs call count for cost visibility.

### 2. `normalize(raw) → list[Posting]`

- Maps SerpAPI fields to `Posting`.
- `company_normalized`: lowercase, strip suffixes (`Inc`, `Ltd`, `LLC`, `S.A.`, `AG`, `Limited`, `plc`, `Corporation`, `Corp`, `Reinsurance Ltd`).
- `country`: derived from location string. Mapping handles `"New York, NY"` → `US`, `"London, UK"` → `GB`, `"Hamilton, Bermuda"` → `BM`, `"Toronto, ON"` → `CA`, `"Ciudad de México, CDMX"` → `MX`.
- `posting_id`: SHA1 of `f"{company_normalized}|{title.lower()}|{country}|{posted_date.isoformat()}"`. Stable.
- Drops rows missing essential fields (company, title, JD body, posted_date) with a counted-error log. If >50% drop → runner hard-fails (likely SerpAPI schema change).

### 3. `filter.apply(postings, run_config) → list[Posting]`

**Hard filters (drop if fail):**
- `skill.hard_match_regex` matches `description` (case-insensitive, word-boundary). For Palantir-insurance: `\b(Foundry|AIP)\b`.
- `posted_date` within `defaults.recency_window_days` (90).
- Any `industry.include_keywords` term appears in `description` OR `title` OR `company`. Keyword list includes both English and Spanish (for MX coverage).
- `company` not in `industry.deny_companies`.

**Classifications (populate, don't drop):**

`role_type` — rule-based on title + description:
- `ENGINEERING`: "engineer", "developer", "architect", "DevOps", "platform"
- `DATA_AI`: "data scientist", "ML", "AI", "analytics", "data engineer"
- `LEADERSHIP`: "head of", "director", "VP", "chief"
- `BUSINESS_OPS`: "analyst", "operations", "consultant", "manager" (when not paired with engineering keywords)
- `OTHER`: fallback

`seniority` — rule-based on title:
- `VP_PLUS`: "VP", "Chief", "President"
- `DIRECTOR`: "Director", "Head of"
- `LEAD`: "Lead", "Principal", "Staff"
- `SENIOR_IC`: "Senior", "Sr."
- `IC`: everything else

Rules are deliberately dumb regex — easy to test, easy to swap for an LLM classifier later (P4 backlog).

### 4. `enrich/firecrawl_jd.fill(postings, run_config) → list[Posting]`

- For each posting with `len(description) < enrichment.firecrawl_min_jd_chars` (500 default), call Firecrawl on `source_url`.
- Replace `description` with the longer scraped body if successful.
- **Returns the postings unchanged in count.** Re-filtering happens in the runner (see below), not here — this keeps `enrich` independent of `filter` so the two modules can be built in parallel.
- Concurrency: sequential at MVP. Async in P3 backlog.
- Firecrawl failures (timeout, 4xx) log warning, keep the truncated description, do not fail the run.

After enrich returns, the runner calls `filter.apply()` a second time on the postings whose descriptions changed. Sometimes a longer JD reveals Foundry/AIP not visible in the truncated version; postings that now fail the skill regex are dropped at this point.

### 5. `dedupe.tag(postings) → list[Posting]`

- For each posting, lookup `posting_id` in `postings` table.
- If exists → `is_new = False`, update `last_seen_at`.
- If new → `is_new = True`, will be inserted by sink.
- Returns full list (nothing dropped — recurring postings are signal, not noise).

### 6. `score.compute(postings, run_config) → list[Posting]`

- `recency_score = max(0, 1.0 - (days_since_posted / recency_window_days))` — linear decay over the window.
- `seniority_score`: `IC=0.20`, `SENIOR_IC=0.40`, `LEAD=0.60`, `DIRECTOR=0.85`, `VP_PLUS=1.00`.
- `score = w_recency * recency_score + w_seniority * seniority_score`. Default weights `0.6 / 0.4`. Configurable in YAML.

### 7. `sink/sqlite.write(postings, run_record) → None`

- One transaction per run.
- Insert `runs` row with status/summary.
- Upsert `postings` rows.
- Insert `posting_run_link` rows with `is_new` and `score`.

### 8. `sink/sheets.write(postings, run_config) → None`

1. Open workbook from env var `GSHEET_WORKBOOK_<RUN_NAME_UPPER>`. Create if missing.
2. Read existing `Companies` + `Postings` tabs into memory.
3. Build edit-preservation maps: `{company: (assigned_to, notes)}` and `{posting_id: (assigned_to, notes)}`.
4. Clear both tabs.
5. Build aggregated Companies rows from postings; write.
6. Write postings rows; merge preserved edits back in.
7. Companies/postings that had non-empty edits but no longer match → append to `Archived` tab.
8. Apply data validation drop-downs on `role_type` and `seniority` columns.

## 7. Error handling

| Failure | Stage | Behavior |
|---|---|---|
| SerpAPI 4xx (auth/quota) | source | Hard fail. Run marked `failed` with error message. UI surfaces. |
| SerpAPI 5xx / network | source | Retry 3x with backoff, then hard fail. |
| Empty result for one geo | source | Log warning, continue with other geos. |
| Empty result across all geos | source | Run completes, status `ok`, 0 results. Summary makes it obvious. |
| Firecrawl failure | enrich | Log warning, keep truncated description, continue. |
| Posting missing required field | normalize | Drop, counted. >50% dropped → hard fail. |
| Google Sheets API failure | sink | SQLite already committed. Run marked `sheet_write_failed`. UI shows "Retry sheet write" button (calls just `sink/sheets`, not the full pipeline). |
| Filter drops everything | filter | Run completes, status `ok`. Summary shows which filter dropped what. |
| Streamlit crash mid-run | runner | SQLite transaction either committed or rolled back atomically. No partial state. |

## 8. UI (Streamlit)

Three pages, navigated via sidebar.

### Page 1: Runs (landing)

Table of all `enabled` runs from `runs.yaml`:

| Run name | Last run | Status | New postings | Total | Actions |
|---|---|---|---|---|---|
| `palantir_insurance` | 2h ago | ✓ ok | 4 new | 27 | [Open Sheet] [Run again] |

"Run again" calls `runner.run(name)` synchronously. `st.status` shows per-stage progress while disabled.

### Page 2: Run detail

- Header: run name, current YAML config, link to Sheet workbook.
- History table: last 10 runs with `started_at`, `duration`, `status`, `new`, `total`, log file link.
- "What's new since last run": top 10 highest-scored `is_new = True` postings. Read-only.
- Last run log: tail of structured log file, expandable.

### Page 3: Browse

Cross-run posting browser. Sidebar filters:
- Run name (multi-select), country, `role_type`, `seniority`, score range, date range, `is_new` only.

Main pane: filterable dataframe with the same columns as the Postings sheet tab. Read-only — partners still edit in Sheets.

## 9. Run configuration (`config/runs.yaml`)

```yaml
defaults:
  recency_window_days: 90
  score_weights:
    recency: 0.6
    seniority: 0.4
  source: serpapi
  enrichment:
    firecrawl_min_jd_chars: 500
  output:
    workbook_id_env_prefix: GSHEET_WORKBOOK_
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
        - seguros           # Spanish, MX coverage
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

## 10. Secrets management

| Secret | Storage | Loaded by |
|---|---|---|
| `SERPAPI_KEY` | `.env` (gitignored) | `config.load_secrets()` at startup |
| `FIRECRAWL_API_KEY` | `.env` | same |
| `GOOGLE_SHEETS_CREDS_PATH` | `.env` → points at JSON in `credentials/` (gitignored) | `gspread` |
| `GSHEET_WORKBOOK_<RUN>` | `.env`, one per run | `config.workbook_id_for(run_name)` |

Pattern: one loader called once at startup. No module reads `os.environ` directly. Easier to mock, easier to swap for a vault (P2 backlog).

`.env.example` checked in with placeholder values documents required keys.

## 11. Logging & observability

- stdlib `logging` with a JSON formatter. No new deps.
- Per-run log file at `data/logs/<run_id>.log`. Streamlit Run detail page tails the latest.
- Every stage emits `stage_started` and `stage_finished` events with input/output counts. `runs.summary` JSON is built from these.
- SerpAPI call count logged per run for spend visibility.
- Real dashboards: P3 backlog.

## 12. Testing strategy

- **Unit tests, deterministic stages** (filter, dedupe, score, normalize, classification rules): JSON fixtures in `tests/fixtures/`. Each test pins exact input → exact output.
- **Integration tests, sources**: mocked `httpx` responses captured from real SerpAPI calls and committed as fixtures. No live network in CI.
- **End-to-end smoke test**: single `pytest` marked `@pytest.mark.e2e` runs `runner.run("palantir_insurance", dry_run=True)` against fixture data, asserts non-empty summary, does not touch live APIs or Sheets.
- **Manual signal-quality test** (`docs/test-queries.md`): runs before code and again after first build with live SerpAPI to confirm parity.

## 13. Deployment posture

| Stage | How | Phase |
|---|---|---|
| MVP | `streamlit run app.py` on Miguel's laptop. Single user. | Day 1 |
| Internal share (small) | Same; Miguel runs on demand, shares Sheet links. | Day 1 |
| Hosted, unauth | Streamlit Community Cloud or Synpulse internal VM. **Requires shared password gate first.** | Backlog P2 |
| Hosted, auth | Reverse proxy + Synpulse SSO. | Backlog P3 |
| Production | Containerized, scheduled runs, audit log, multi-user roles. | Backlog P4 |

## 14. Build decomposition (multi-agent execution)

The module boundaries above are designed to allow parallel agent work. Each work package owns a closed set of files, depends only on the shared `models.py` types and the fixture protocol, and can be built and tested independently.

### Phase 0 — Foundation (serial, single agent)

Blocks everything else. Establishes the contracts other workstreams build against.

**Files owned:**
- `pyproject.toml`, `.env.example`, `.gitignore`, `README.md` updates
- `src/job_identifier/models.py` — `Posting`, `RunConfig`, `RunResult`, enums
- `src/job_identifier/config.py` — pydantic schema + `load_secrets()`
- `config/runs.yaml` — committed with the `palantir_insurance` run
- `tests/fixtures/` — `raw_serpapi_sample.json`, `normalized_postings_sample.json`, `filtered_postings_sample.json` (each fixture shows what a stage's output looks like)
- `tests/conftest.py` — pytest fixtures loading the JSON samples

**Exit criteria:**
- `from job_identifier.models import Posting` works
- `config.load_runs("config/runs.yaml")` returns a validated `list[RunConfig]`
- Sample fixtures load via `pytest fixtures` without errors

### Phase 1 — Parallel workstreams (5 agents)

Each agent works in an isolated branch. All consume `Posting` / fixtures from Phase 0.

| WS | Agent owns | Depends on | Verifies via |
|---|---|---|---|
| **A — Source + Normalize** | `sources/serpapi_jobs.py`, `normalize.py`, `tests/test_normalize.py`, `tests/test_source_serpapi.py` (mocked HTTP) | `models`, `config` | Output matches `normalized_postings_sample.json` fixture |
| **B — Filter + Score** | `filter.py`, `score.py`, `tests/test_filter.py`, `tests/test_score.py` | `models`, `config` | Filter input = `normalized_postings_sample.json`, output = `filtered_postings_sample.json`. Score test fixtures lock numeric thresholds. |
| **C — Store + Dedupe + SQLite sink** | `store.py`, `dedupe.py`, `sink/sqlite.py`, `tests/test_store.py`, `tests/test_dedupe.py`, `tests/test_sink_sqlite.py` | `models` | Tests use `:memory:` SQLite + sample postings |
| **D — Enrich** | `enrich/firecrawl_jd.py`, `tests/test_enrich.py` (mocked Firecrawl) | `models` only | Tests assert short-JD postings get re-fetched with longer descriptions returned. Re-filtering is the runner's job, tested separately in Phase 2. |
| **E — Sheet sink** | `sink/sheets.py`, `tests/test_sink_sheets.py` (mocked gspread) | `models`, `config` | Tests assert edit preservation across two consecutive writes |

**Inter-workstream protocol:** the only thing crossing workstream boundaries is the `Posting` dataclass and the fixture JSON files. No workstream may import from another workstream's modules except through `models` and `config`.

**Conflict avoidance:**
- File ownership is exclusive per workstream — no two agents write the same file.
- Tests are colocated with the workstream they verify, no shared test files.
- If a workstream needs a new helper that doesn't exist yet, it adds the helper to its own module, not to a shared `utils.py`.

### Phase 2 — Integration (serial, single agent)

After Phase 1 workstreams are merged:

**Files owned:**
- `runner.py` — composes all stages, owns the error matrix
- `cli.py` — `typer` app
- `tests/test_runner.py` — e2e smoke test using only fixtures (no live APIs)

**Exit criteria:** `job-id run palantir_insurance --dry-run` against fixture data completes successfully with a summary count matching the fixture's expected output.

### Phase 3 — UI (one agent, can start during Phase 2)

**Files owned:**
- `app.py` — Streamlit entry point
- `ui/pages/01_runs.py`, `ui/pages/02_run_detail.py`, `ui/pages/03_browse.py`
- `ui/components/` — shared widgets (run table, posting card)

**Depends on:** Phase 2's `runner.run()` and Phase 1-C's `store` for queries. Can be developed against a stub `runner` until Phase 2 lands.

### Phase 4 — Live test + sign-off (serial)

- Run `docs/test-queries.md` queries against the built pipeline.
- Compare signal counts against the manual test baseline.
- Tune `runs.yaml` keyword lists if signal quality is off.
- Partner walkthrough.

### Phase ordering summary

```
Phase 0 (Foundation, serial)
   │
   ▼
Phase 1 (5 agents in parallel: A, B, C, D, E)
   │
   ▼
Phase 2 (Integration, serial)
   │
   ├──────────────► Phase 3 (UI, can start during Phase 2)
   ▼
Phase 4 (Live test + sign-off)
```

## 15. Dependencies

| Lib | Purpose |
|---|---|
| `python-dotenv` | Loads `.env` for CLI + Streamlit |
| `pydantic` | Validates `runs.yaml` |
| `pyyaml` | Reads `runs.yaml` |
| `typer` | CLI |
| `httpx` | All HTTP |
| `google-search-results` | SerpAPI SDK |
| `firecrawl-py` | Firecrawl SDK |
| `gspread` + `google-auth` | Sheets writes |
| `streamlit` | UI |
| `sqlite-utils` | SQLite ergonomics |
| `pytest` + `pytest-mock` | Tests |
| `ruff` + `mypy` (dev) | Lint + type checks |

## 16. Out of scope for MVP (cross-reference to `PLAN.md` backlog)

- Company enrichment (Apollo/Clearbit) → P1
- Scheduled runs → P2
- UI auth + hosting → P2/P3
- Apify + ATS direct crawl → P3
- LLM-based JD classification → P4
- CRM push (HubSpot/Salesforce) → P5
- Streamlit inline editing of partner annotations → never (Sheet remains the editable surface)

## 17. Open questions / known assumptions

- **Synpulse legal review** on scraping job postings via SerpAPI — assumed OK since SerpAPI is a licensed wrapper around Google's public Jobs aggregator, but worth a sanity check before broad partner rollout.
- **MX language coverage**: keyword list includes Spanish industry terms, but role_type/seniority classification is English-only. Acceptable for MVP; Spanish title classification → P4 along with LLM classification.
- **Workbook auto-creation**: requires the service account to have Drive write permission to a parent folder. Assumed Miguel will create one shared "Job Identifier" folder and grant the service account access at setup.
