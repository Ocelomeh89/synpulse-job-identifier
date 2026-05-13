# Manual signal-quality test — Palantir × Insurance

Run these before writing any code. The goal is to verify that SerpAPI Google Jobs returns enough relevant postings per geo to be worth automating. If a geo returns <5 plausible matches across all variants, we know to substitute another source (e.g. Firecrawl on specific company ATSes) for that region.

## Setup

1. Sign up at https://serpapi.com → grab API key.
2. Export it: `export SERPAPI_KEY=...`
3. Test calls below use `curl` so you can paste into terminal directly. SerpAPI also has a free Playground UI at https://serpapi.com/playground if you prefer.

## Notes on Google Jobs query behavior

- Boolean operators (`OR`, quotes, parens) work but Google interprets them loosely — expect over-matching.
- `location` must be a Google-recognized place name. Country names work; `"Bermuda"` works.
- Results often duplicate across boards (Indeed, LinkedIn, company ATS) — dedupe later by `company + title`.
- `chips` param can filter by `date_posted:week` etc. — we'll add in code, not here.
- API returns max ~10 results per call; use `next_page_token` for more.

## Test matrix

Run each query. For each, count:
- **Total results** returned
- **Plausible matches**: insurance/reinsurance/broker company in `company_name` OR insurance keyword in description
- **False positives**: Palantir Technologies itself, consultancies (Accenture/Deloitte/IBM), unrelated industries

### Query A — "Palantir Foundry" + insurance, broad geo sweep

```bash
# US
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q="Palantir Foundry" insurance' \
  --data-urlencode 'location=United States' \
  --data-urlencode "api_key=$SERPAPI_KEY"

# Canada
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q="Palantir Foundry" insurance' \
  --data-urlencode 'location=Canada' \
  --data-urlencode "api_key=$SERPAPI_KEY"

# Mexico
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q="Palantir Foundry" insurance' \
  --data-urlencode 'location=Mexico' \
  --data-urlencode "api_key=$SERPAPI_KEY"

# UK
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q="Palantir Foundry" insurance' \
  --data-urlencode 'location=United Kingdom' \
  --data-urlencode "api_key=$SERPAPI_KEY"

# Bermuda
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q="Palantir Foundry" insurance' \
  --data-urlencode 'location=Bermuda' \
  --data-urlencode "api_key=$SERPAPI_KEY"
```

### Query B — AIP variant (newer product, smaller signal but cleaner)

```bash
# Just US + UK as the two most likely hits
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q="Palantir AIP" insurance' \
  --data-urlencode 'location=United States' \
  --data-urlencode "api_key=$SERPAPI_KEY"

curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q="Palantir AIP" insurance' \
  --data-urlencode 'location=United Kingdom' \
  --data-urlencode "api_key=$SERPAPI_KEY"
```

### Query C — Reinsurance angle (UK + Bermuda are global hubs)

Bermuda's economy is heavily reinsurance — this is where the Bermuda geo earns its place in MVP scope.

```bash
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q=Palantir reinsurance' \
  --data-urlencode 'location=Bermuda' \
  --data-urlencode "api_key=$SERPAPI_KEY"

curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q=Palantir reinsurance' \
  --data-urlencode 'location=United Kingdom' \
  --data-urlencode "api_key=$SERPAPI_KEY"
```

### Query D — Skill-only, no industry seed (for recall comparison)

Useful baseline: how much does adding "insurance" to the query cost us in recall? If a lot, we'd switch to broad skill search + industry post-filter.

```bash
curl -G "https://serpapi.com/search.json" \
  --data-urlencode 'engine=google_jobs' \
  --data-urlencode 'q=Palantir Foundry' \
  --data-urlencode 'location=United States' \
  --data-urlencode "api_key=$SERPAPI_KEY" \
  | jq '.jobs_results | length, [.[] | {company: .company_name, title}]'
```

## What to record

After running, fill this in (rough is fine):

| Query | Geo | Total results | Plausible | False positive % | Notes |
|---|---|---|---|---|---|
| A | US | | | | |
| A | CA | | | | |
| A | MX | | | | |
| A | UK | | | | |
| A | BM | | | | |
| B | US | | | | |
| B | UK | | | | |
| C | BM | | | | |
| C | UK | | | | |
| D | US | | | | |

## Decision rules

- **Plausible ≥ 10 across all geos combined for Query A** → SerpAPI is viable as primary source. Proceed to build MVP.
- **Plausible 3–9** → SerpAPI works but we need broader skill terms (drop quoted phrase, expand to `Palantir OR Foundry OR AIP`) or move industry from query to post-filter.
- **Plausible < 3** → Google Jobs index is too thin for this combo. Pivot: target Greenhouse/Lever/Workday boards of known carriers via Firecrawl instead.
- **False positive rate > 50%** on Query A → the in-query industry seed isn't doing useful work; switch to Query D pattern (broad skill, JD-body industry filter).
