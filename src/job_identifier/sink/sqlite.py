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
