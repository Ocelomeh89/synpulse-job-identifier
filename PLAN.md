# Job Identifier — MVP Plan

## Goal
Turn public job postings into a sales-trigger list: which companies (filtered by industry) are hiring for a given skill/technology right now.

First use case: insurance companies hiring for Palantir (Foundry / AIP / Apollo).
The pipeline is generic — `skill` and `industry` are inputs.

## MVP scope

| Decision | Choice |
|---|---|
| Geographies | US, Canada, Mexico, UK, Bermuda |
| Discovery source | SerpAPI Google Jobs |
| Depth/enrichment | Firecrawl on the original posting URL when JD body is truncated |
| Output | Google Sheet (one tab per `skill × industry` run) |
| Trigger | Manual (CLI command or notebook) |
| Enrichment | Placeholder column (`company_domain`, `company_size`, `hq_country` left blank) — see backlog |
| Storage | Local SQLite for dedupe / run history; Sheet is the human-facing surface |

## Pipeline

```
config (skill, industry, geo[])
  → SerpAPI Google Jobs search (one query per geo)
  → normalize: company, title, location, posted_date, job_url, jd_excerpt
  → Firecrawl fallback on rows with short JD (<500 chars)
  → keyword filter: skill terms appear in JD body
  → industry filter: heuristic (company name allow/deny list + JD keywords like "insurer", "carrier", "reinsurance")
  → dedupe: (normalized_company_name, title, location) within last 30 days
  → score: recency + # of related roles per company + seniority hint
  → write to Google Sheet
```

## Config shape (one YAML file, checked in)

```yaml
runs:
  - name: palantir_insurance
    skill:
      include: ["Palantir", "Foundry", "AIP", "Apollo"]
      exclude: ["Palantir Technologies"]   # filter out Palantir's own postings
    industry:
      include_keywords: ["insurance", "insurer", "carrier", "reinsurance", "underwriting", "claims"]
      deny_companies: ["Palantir Technologies", "IBM", "Accenture", "Deloitte"]  # consultancies/vendors
    geos: ["US", "CA", "MX", "UK", "BM"]
    output_sheet_tab: "Palantir × Insurance"
```

## Output sheet columns

`company` · `title` · `location` · `country` · `posted_date` · `seniority` · `skill_match` · `jd_excerpt` · `job_url` · `score` · `company_domain` *(enrichment placeholder)* · `company_size` *(placeholder)* · `notes`

## Cost ballpark (MVP)
- SerpAPI: ~$50/mo (5k searches) — plenty for manual runs
- Firecrawl: free tier likely sufficient for fallback enrichment
- Google Sheets API: free
- Total: ~$50/mo

---

# Tech stack

| Concern | Pick | Why |
|---|---|---|
| Language | Python 3.11+ | Best SDK coverage for SerpAPI / Firecrawl / Sheets; pandas-friendly for spot-checking |
| Env / deps | `uv` + `pyproject.toml` | Fast, reproducible, no venv ceremony |
| Config | `pydantic` + `PyYAML` | Typed config from `config/runs.yaml` |
| CLI | `typer` | Auto-generates `--help`, easy subcommands |
| HTTP | `httpx` | Async if we want concurrent geo fetches later |
| Discovery | `google-search-results` (SerpAPI Python SDK) | Official |
| Enrichment | `firecrawl-py` | Official SDK |
| Storage | `sqlite-utils` | Schema-less inserts, ergonomic for prototyping |
| Sheets sink | `gspread` + `google-auth` | Standard combo |
| Tests | `pytest` | — |

## Directory scaffold

```
synpulse-job-identifier/
├── PLAN.md
├── README.md
├── pyproject.toml
├── .env.example                 # SERPAPI_KEY, FIRECRAWL_KEY, GOOGLE_SHEETS_CREDS_PATH
├── .gitignore                   # ignores .env, data/*.sqlite, .venv
├── config/
│   └── runs.yaml                # skill × industry × geo configs
├── credentials/                 # gitignored — Google service-account JSON lives here
├── data/
│   └── job_identifier.sqlite    # gitignored
├── docs/
│   └── test-queries.md
├── src/
│   └── job_identifier/
│       ├── __init__.py
│       ├── cli.py               # `job-id run <run-name>` / `job-id list-runs`
│       ├── config.py            # parse + validate runs.yaml
│       ├── models.py            # Posting, RunResult dataclasses
│       ├── sources/
│       │   ├── __init__.py
│       │   └── serpapi_jobs.py
│       ├── enrich/
│       │   ├── __init__.py
│       │   └── firecrawl_jd.py  # fallback for truncated JDs
│       ├── filter.py            # skill match + industry heuristic
│       ├── dedupe.py            # uses SQLite for cross-run dedupe
│       ├── score.py
│       ├── sink/
│       │   ├── __init__.py
│       │   └── sheets.py
│       └── store.py             # SQLite wrapper
└── tests/
    ├── test_filter.py
    └── fixtures/
        └── sample_jobs.json     # canned SerpAPI responses for offline testing
```

## CLI shape (target)

```bash
job-id list-runs                          # show configured runs from runs.yaml
job-id run palantir_insurance             # execute one run, write to Sheet
job-id run palantir_insurance --dry-run   # fetch + filter, print to stdout, no Sheet write
job-id run palantir_insurance --geo US    # restrict to one geo for testing
```


# Backlog (post-MVP)

## P1 — Enrichment
- [ ] Company enrichment integration (evaluate Apollo, Clearbit, ZoomInfo, People Data Labs) — adds domain, size, HQ country, revenue band
- [ ] Auto-detect industry from enrichment data (replace keyword heuristic)
- [ ] LinkedIn company URL lookup for SDR handoff

## P2 — Scheduling & ops
- [ ] Per-keyword schedule (cron-style: e.g. `palantir_insurance` weekly, `snowflake_retail` daily)
- [ ] Run history dashboard (last run, # results, deltas vs previous run)
- [ ] Diff view in Sheet: highlight new postings since last run
- [ ] Slack/email notification on new high-score matches

## P3 — Source expansion
- [ ] Apify LinkedIn Jobs actor as secondary source (better seniority + applicant data)
- [ ] Direct ATS crawling via Firecrawl (Greenhouse, Lever, Workday boards) for target companies
- [ ] Industry-specific job boards (e.g. insurancejobs.com)

## P4 — Intelligence layer
- [ ] LLM-based JD classification: replace regex skill match with structured extraction (skill, seniority, tech adjacency, team context)
- [ ] Cluster postings per company to infer team size / investment level
- [ ] Track posting velocity per company over time (rising signal vs steady state)
- [ ] Cross-reference with funding/news data for ICP scoring

## P5 — Product surface
- [ ] Web UI to launch runs and browse results (replaces Sheet for power users)
- [ ] Saved "playbooks" — pre-configured skill × industry combos
- [ ] CRM push (HubSpot/Salesforce) instead of Sheet
- [ ] Multi-user / role-based access

## P6 — Compliance & quality
- [ ] Respect robots.txt and source ToS — document data lineage per source
- [ ] PII filter on JD text before storage
- [ ] Geo expansion (EMEA broadly, APAC)
