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
