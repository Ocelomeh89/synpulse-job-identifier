from job_identifier.config import load_secrets


def test_load_secrets_from_env(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "sk_serp")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "sk_fc")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", "credentials/sa.json")
    monkeypatch.setenv("GSHEET_WORKBOOK_PALANTIR_INSURANCE", "abc123")

    s = load_secrets(run_names=["palantir_insurance"])
    assert s.serpapi_key == "sk_serp"
    assert s.firecrawl_api_key == "sk_fc"
    assert s.google_sheets_creds_path == "credentials/sa.json"
    assert s.workbook_ids_by_run == {"palantir_insurance": "abc123"}


def test_load_secrets_missing_serpapi_raises(monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", "x")
    monkeypatch.setenv("GSHEET_WORKBOOK_FOO", "x")

    try:
        load_secrets(run_names=["foo"])
    except RuntimeError as e:
        assert "SERPAPI_KEY" in str(e)
    else:
        raise AssertionError("Expected RuntimeError")
