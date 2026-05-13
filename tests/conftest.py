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
