# synpulse-job-identifier — Project Context for Claude

> **For any Claude session starting in this worktree:** this file is the entry point. Read it first, then `docs/superpowers/specs/2026-05-13-job-identifier-design.md` for the full spec and `docs/superpowers/plans/2026-05-13-job-identifier.md` for the implementation plan.

## What this project is

Internal Synpulse sales-intelligence tool. Mines public job postings to identify companies hiring for a given skill+industry combo — those are sales triggers for Synpulse's consulting practice. First use case: insurance companies hiring for Palantir Foundry or AIP across US/CA/MX/UK/BM.

The pipeline is generic — `skill` and `industry` are config in `config/runs.yaml`, not code. The same pipeline runs unmodified for Snowflake@retailers, Salesforce@fintechs, etc.

## Current status (2026-05-13)

**Phase 0–3 implementation: COMPLETE.** 31 commits on branch `worktree-job-identifier-mvp`, branched from `main` HEAD `94e484d`. 85/85 pytest, ruff clean. Not yet merged to main.

**Phase 4 (live signal test + partner walkthrough): NOT STARTED.** Requires real API keys and Miguel's manual smoke. See "Phase 4 checklist" below.

## File map

```
worktree-job-identifier-mvp/
├── CLAUDE.md                                            ← you are here
├── PLAN.md                                              ← product overview + backlog
├── pyproject.toml, .env.example, .gitignore
├── config/runs.yaml                                     ← skill/industry/geo config
├── docs/
│   ├── test-queries.md                                  ← manual SerpAPI signal test
│   └── superpowers/
│       ├── specs/2026-05-13-job-identifier-design.md    ← full design spec
│       └── plans/2026-05-13-job-identifier.md           ← phased TDD implementation plan
├── src/job_identifier/
│   ├── models.py             ← Posting, RunConfig, RunResult, enums
│   ├── config.py             ← load_runs (YAML+pydantic) + load_secrets (.env)
│   ├── country.py            ← location → ISO-2 country
│   ├── normalize.py          ← raw SerpAPI → Posting
│   ├── filter.py             ← skill regex, industry, deny-list, role/seniority classifiers, apply()
│   ├── score.py              ← recency-decay × seniority bucket, apply()
│   ├── store.py              ← SQLite schema + run/posting/link CRUD
│   ├── dedupe.py             ← tag_is_new
│   ├── logging_setup.py      ← JSON-formatted per-run logs to data/logs/<run_id>.log
│   ├── runner.py             ← pipeline composition + error matrix
│   ├── cli.py                ← `job-id list-runs` / `job-id run`
│   ├── sources/serpapi_jobs.py
│   ├── enrich/firecrawl_jd.py
│   ├── sink/sqlite.py
│   ├── sink/sheets.py        ← aggregate/build rows + edit preservation + GspreadWorkbook
│   └── ui/
│       ├── app.py            ← Streamlit entry
│       └── pages/
│           ├── 01_Runs.py
│           ├── 02_Run_detail.py
│           └── 03_Browse.py
├── tests/                    ← 22 test files, fixtures in tests/fixtures/
└── data/                     ← gitignored: jobs.db + logs/

```

## What's been built (per phase)

### Phase 0 — Foundation (5 tasks, all committed)
- Project scaffolding, deps, `.env.example`, `.gitignore`
- `Posting` dataclass + enums (frozen, with `to_dict`/`from_dict` roundtrip)
- `RunConfig` pydantic-validated config loader from `config/runs.yaml`
- `Secrets` loader from `.env` with required-var validation
- Test fixtures (`raw_serpapi_sample.json`, `normalized_postings_sample.json`, `filtered_postings_sample.json`) + conftest

### Phase 1 — Five parallel workstreams (14 tasks, all committed)
- **A: Source + Normalize** — SerpAPI client with pagination/retry, country mapper, posting_id SHA1 hash
- **B: Filter + Score** — skill regex matcher, role_type/seniority classifiers (rule-based), industry+deny-list, `filter.apply()` composition, recency+seniority+combined score
- **C: Store + Dedupe + SQLite sink** — `Store` class with monkey-patched methods (`upsert_posting`, `record_run`, `link_posting_to_run`, `last_run_for_name`), `dedupe.tag_is_new`, `write_run` orchestrator
- **D: Enrich** — `fill_short_descriptions` via Firecrawl with safe fallback
- **E: Sheets sink** — `aggregate_companies`, `build_postings_rows`, `merge_preserved_edits`, `write_sheets`, concrete `GspreadWorkbook`

### Phase 2 — Integration (3 tasks, all committed)
- `runner.py` — composes the full pipeline: source → normalize → filter → enrich → re-filter changed → dedupe → score → sqlite-sink → sheets-sink (with `sheet_write_failed` graceful path)
- `cli.py` — typer commands `list-runs` and `run` (with `--dry-run`, `--config`, `--db`)
- `logging_setup.py` — JSON-formatted per-run log files

### Phase 3 — Streamlit UI (3 tasks, all committed)
- Entry `ui/app.py` + 3 pages:
  - `01_Runs.py` — landing: status table + trigger panel with `st.status` progress
  - `02_Run_detail.py` — config view, last-10 history, "what's new", log tail
  - `03_Browse.py` — cross-run dataframe with sidebar filters (country, role_type, seniority, score range)

## Tests

- **85 passing** (`pytest -q`).
- Unit tests cover every deterministic stage (normalize, filter, score, dedupe, store, sheets aggregation, sheets edit-preservation, enrich, logging).
- Integration tests: runner end-to-end with mocked SerpAPI/Firecrawl/gspread.
- No live-API tests — those are Phase 4.

## Known notes (not blockers, captured in code reviews)

These came up during quality reviews. None block MVP; document as future work:

- `runner.run()` uses `zip(filtered, enriched)` — safe today since `fill_short_descriptions` never drops, but a dict-keyed diff would be more robust if enrich behavior changes.
- `runner.run()` uses `datetime.now()` for `finished_at` (not injected). Tests don't assert on this; fine for MVP.
- SQLite sink `write_run` issues separate inserts; not wrapped in a transaction. Idempotent on replay, but a partial-write is possible mid-loop on hardware failure.
- CLI `cli.py` calls `logging.basicConfig` at module load. Could conflict if cli is imported into something else that owns logging. Fine when used as `job-id` entry point.
- SerpAPI source retries on bare `except Exception` — broad. KeyboardInterrupt is safe (inherits BaseException), but narrowing to specific httpx errors would be cleaner.
- GspreadWorkbook integration is untested in CI (requires live API). Verified manually in Phase 4.

## Phase 4 checklist (Miguel-owned, not started)

1. **Get API credentials**
   - SerpAPI key from https://serpapi.com (free tier OK for first run)
   - Firecrawl key from https://firecrawl.dev (free tier OK)
2. **Create a Google Sheet**
   - Create a new empty workbook named "Job Identifier — Palantir × Insurance" (or similar).
   - Create a Google Cloud service account, download the JSON key, save to `credentials/service-account.json` (gitignored).
   - Share the workbook with the service account email (`...@<project>.iam.gserviceaccount.com`) as Editor.
   - Copy the workbook ID from the URL (the long string between `/d/` and `/edit`).
3. **Populate `.env`**
   ```bash
   cp .env.example .env
   # Edit .env with:
   # SERPAPI_KEY=<your key>
   # FIRECRAWL_API_KEY=<your key>
   # GOOGLE_SHEETS_CREDS_PATH=credentials/service-account.json
   # GSHEET_WORKBOOK_PALANTIR_INSURANCE=<the workbook ID>
   ```
4. **Smoke test (dry-run, no Sheet write, no Firecrawl)**
   ```bash
   source .venv/bin/activate
   job-id run palantir_insurance --dry-run
   ```
   Expected: prints summary with `fetched`, `normalized`, `filtered`, `scored` counts. If `fetched=0` across all geos, see `docs/test-queries.md` — likely the query needs tuning in `runs.yaml`.
5. **Live run**
   ```bash
   job-id run palantir_insurance
   ```
   Expected: populates the Sheet with two tabs (Companies + Postings), plus an Archived tab when partner edits get orphaned on a future re-run.
6. **Streamlit UI test**
   ```bash
   streamlit run src/job_identifier/ui/app.py
   ```
   Opens browser at http://localhost:8501. Verify all three pages render and the "Run now" button works end-to-end.
7. **Partner walkthrough** — share the Sheet with one Synpulse partner, get reactions on the Companies tab columns + scoring.
8. **Tune `config/runs.yaml`** if signal quality is off (see decision rules in `docs/test-queries.md`).

## Backlog (post-MVP, in `PLAN.md`)

- P1: Company enrichment via Apollo/Clearbit/ZoomInfo
- P2: Scheduled runs (cron per skill), UI auth + hosting
- P3: Apify LinkedIn source, ATS direct crawl via Firecrawl
- P4: LLM-based JD classification (replacing rule-based)
- P5: CRM push (HubSpot/Salesforce)
- P6: Compliance review, geo expansion, multi-tenant

## How to resume in a new Claude session

1. **Open the terminal at the worktree path:**
   ```bash
   cd /Users/miguelgraf/Documents/GitHub/synpulse-job-identifier/.claude/worktrees/job-identifier-mvp
   ```
   (The worktree should still exist on disk. If for some reason it was removed, recreate from the branch: `git worktree add .claude/worktrees/job-identifier-mvp worktree-job-identifier-mvp` from the main repo.)

2. **Start Claude Code from that directory.** Claude will read this `CLAUDE.md` automatically and the spec/plan are discoverable via `docs/superpowers/`.

3. **Tell Claude what you want to do next.** Common starting prompts:
   - "Resume Phase 4 — I've populated `.env`, walk me through the dry-run."
   - "I ran the dry-run and got X results, here's the output — diagnose."
   - "Merge the worktree to main and tag v0.1.0."
   - "I want to add a second run, `snowflake_retail`. Help me configure `runs.yaml`."
   - "Implement P1 backlog: company enrichment via Apollo."

4. **Memory.** Project + user memory is stored at `~/.claude/projects/-Users-miguelgraf-Documents-GitHub-synpulse-job-identifier/memory/`. The new Claude session will load `MEMORY.md` automatically.

## Commit history (most recent first)

```
4a9f8b7 chore: remove unused imports and mark gspread lazy imports
b1a0992 feat(ui): browse page with filterable postings dataframe
1f9bf58 feat(ui): run-detail page with history + diff
277d9d7 feat(ui): Streamlit entry + Runs landing page
6366578 feat(logging): JSON-formatted per-run log files in data/logs/
4390b5a feat(cli): list-runs and run commands via typer
91b9f14 feat(runner): compose pipeline stages, handle error matrix
1cf5b5b feat(sink/sheets): add gspread-backed Workbook implementation
cc0e9a3 fix(sink/sheets): sample_jd_url uses most recent posting per spec
a49b11e feat(sink/sheets): write_sheets orchestrator with edit preservation
f205c8d feat(sink/sheets): build Postings rows + edit-preservation merge
edd7094 feat(sink/sheets): aggregate postings into Companies rows
62b4690 feat(enrich): refill short JDs via Firecrawl with safe fallback
2a01baf feat(sink/sqlite): atomic write of postings + run + links
f463e6e feat(dedupe): tag is_new against Store
4724a63 feat(store): record_run + link_posting_to_run + last_run_for_name
dffb333 feat(store): upsert + lookup for postings
146b482 feat(store): SQLite schema for postings, runs, posting_run_link
c927339 feat(score): recency-decay + seniority-bucket combined score
0ce3623 feat(filter): apply() composes hard filters and classification
e7cc71b feat(filter): industry keyword + deny-list match
bb61ee0 feat(filter): role_type + seniority classifiers
35568c2 feat(filter): skill regex match + excerpt builder
009505b feat(source): SerpAPI Google Jobs client with retry + pagination
b031c5f feat(normalize): map raw SerpAPI jobs to Posting dataclass
eb60e46 feat(country): map location strings to ISO-2 codes
fcb6d01 test: add SerpAPI/normalized/filtered fixtures for Phase 1 workstreams
feea2a8 feat(config): add load_secrets with required-env validation
5faadfe feat(config): load and validate runs.yaml via pydantic
e5ddb20 feat(models): add Posting, RunConfig, Secrets, enums
58ca45f chore: scaffold project structure and dependencies
94e484d Add phased implementation plan with TDD steps             ← main HEAD
c59abf2 Add MVP design spec, plan, and signal-quality test queries
37ceacf Initial commit
```
