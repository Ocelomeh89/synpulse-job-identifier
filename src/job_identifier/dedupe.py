from __future__ import annotations
from dataclasses import replace

from job_identifier.models import Posting
from job_identifier.store import Store


def tag_is_new(postings: list[Posting], store: Store) -> list[Posting]:
    return [
        replace(p, is_new=not store.posting_exists(p.posting_id))
        for p in postings
    ]
