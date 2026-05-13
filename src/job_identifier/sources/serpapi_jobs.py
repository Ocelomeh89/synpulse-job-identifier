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
