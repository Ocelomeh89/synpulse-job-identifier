from pathlib import Path

from job_identifier.config import load_secrets

# Suppress auto-loading of a real .env file in the project root during tests.
NO_DOTENV = Path("/dev/null")


def test_load_secrets_from_env(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "sk_serp")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "sk_fc")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", "credentials/sa.json")
    monkeypatch.delenv("GOOGLE_SHEETS_CREDS_JSON", raising=False)
    monkeypatch.setenv("GSHEET_WORKBOOK_PALANTIR_INSURANCE", "abc123")

    s = load_secrets(run_names=["palantir_insurance"], dotenv_path=NO_DOTENV)
    assert s.serpapi_key == "sk_serp"
    assert s.firecrawl_api_key == "sk_fc"
    assert s.google_sheets_creds_path == "credentials/sa.json"
    assert s.google_sheets_creds_json is None
    assert s.workbook_ids_by_run == {"palantir_insurance": "abc123"}


def test_load_secrets_accepts_inline_json(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "sk_serp")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "sk_fc")
    monkeypatch.delenv("GOOGLE_SHEETS_CREDS_PATH", raising=False)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_JSON", '{"type":"service_account"}')
    monkeypatch.setenv("GSHEET_WORKBOOK_PALANTIR_INSURANCE", "abc123")

    s = load_secrets(run_names=["palantir_insurance"], dotenv_path=NO_DOTENV)
    assert s.google_sheets_creds_path is None
    assert s.google_sheets_creds_json == '{"type":"service_account"}'


def test_load_secrets_missing_both_creds_raises(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "x")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "x")
    monkeypatch.delenv("GOOGLE_SHEETS_CREDS_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_CREDS_JSON", raising=False)
    monkeypatch.setenv("GSHEET_WORKBOOK_FOO", "x")

    try:
        load_secrets(run_names=["foo"], dotenv_path=NO_DOTENV)
    except RuntimeError as e:
        assert "GOOGLE_SHEETS_CREDS" in str(e)
    else:
        raise AssertionError("Expected RuntimeError")


def test_load_secrets_missing_serpapi_raises(monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", "x")
    monkeypatch.setenv("GSHEET_WORKBOOK_FOO", "x")

    try:
        load_secrets(run_names=["foo"], dotenv_path=NO_DOTENV)
    except RuntimeError as e:
        assert "SERPAPI_KEY" in str(e)
    else:
        raise AssertionError("Expected RuntimeError")
