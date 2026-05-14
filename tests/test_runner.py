from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from job_identifier.config import load_runs
from job_identifier.runner import run
from job_identifier.store import Store


def test_runner_happy_path(raw_serpapi_response, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "job_identifier.runner.fetch_jobs",
        lambda cfg, api_key: [raw_serpapi_response],
    )

    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = []
    workbook.postings_tab.read_rows.return_value = []
    monkeypatch.setattr(
        "job_identifier.runner.open_workbook",
        lambda run_name, secrets, output_config: workbook,
    )

    monkeypatch.setattr(
        "job_identifier.runner.firecrawl_client",
        lambda secrets: MagicMock(scrape_url=MagicMock(return_value={"markdown": ""})),
    )

    store = Store(str(tmp_path / "test.db"))
    store.init_schema()

    config_path = Path(__file__).parent.parent / "config" / "runs.yaml"
    runs = load_runs(config_path)
    secrets = MagicMock(serpapi_key="x", firecrawl_api_key="x")

    result = run(
        run_config=runs[0],
        secrets=secrets,
        store=store,
        now=datetime(2026, 5, 13, 10, 0, 0),
    )

    assert result.status == "ok"
    assert result.summary["fetched"] >= 1
    assert result.summary["filtered"] >= 1
    assert result.summary["scored"] == result.summary["filtered"]
    workbook.companies_tab.write_rows.assert_called_once()


def test_runner_dry_run_skips_sinks(raw_serpapi_response, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "job_identifier.runner.fetch_jobs",
        lambda cfg, api_key: [raw_serpapi_response],
    )
    workbook = MagicMock()
    monkeypatch.setattr(
        "job_identifier.runner.open_workbook",
        lambda run_name, secrets, output_config: workbook,
    )
    monkeypatch.setattr(
        "job_identifier.runner.firecrawl_client",
        lambda secrets: MagicMock(scrape_url=MagicMock(return_value={"markdown": ""})),
    )

    store = Store(str(tmp_path / "test.db"))
    store.init_schema()

    config_path = Path(__file__).parent.parent / "config" / "runs.yaml"
    runs = load_runs(config_path)
    result = run(
        run_config=runs[0],
        secrets=MagicMock(),
        store=store,
        now=datetime(2026, 5, 13),
        dry_run=True,
    )

    assert result.status == "ok"
    workbook.companies_tab.write_rows.assert_not_called()
    assert len(list(store.db["runs"].rows)) == 0
