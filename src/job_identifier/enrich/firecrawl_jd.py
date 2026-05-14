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
