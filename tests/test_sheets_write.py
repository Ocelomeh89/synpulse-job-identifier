from datetime import date, datetime
from unittest.mock import MagicMock
from job_identifier.models import (
    OutputConfig, Posting, RoleType, Seniority,
)
from job_identifier.sink.sheets import write_sheets


def _p(pid: str, score: float = 0.5) -> Posting:
    return Posting(
        posting_id=pid, source="s", source_url=f"https://x.com/{pid}",
        fetched_at=datetime(2026, 5, 13),
        title="Foundry Engineer", company="Acme", company_normalized="acme",
        location="NYC", country="US", posted_date=date(2026, 5, 10),
        description="d", description_excerpt="...Foundry...",
        skill_matches=["Foundry"], industry_match=True,
        role_type=RoleType.ENGINEERING, seniority=Seniority.IC,
        recency_score=0.0, seniority_score=0.0, score=score, is_new=True,
    )


def test_write_sheets_calls_clear_and_update():
    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = []
    workbook.postings_tab.read_rows.return_value = []

    output = OutputConfig(
        companies_tab="Companies", postings_tab="Postings", archived_tab="Archived",
    )
    write_sheets(workbook=workbook, postings=[_p("a")], output_config=output)

    workbook.companies_tab.clear.assert_called_once()
    workbook.companies_tab.write_rows.assert_called_once()
    workbook.postings_tab.clear.assert_called_once()
    workbook.postings_tab.write_rows.assert_called_once()


def test_write_sheets_preserves_edits():
    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = [
        {"company": "Acme", "assigned_to": "alice", "notes": "ping"}
    ]
    workbook.postings_tab.read_rows.return_value = []

    output = OutputConfig(
        companies_tab="Companies", postings_tab="Postings", archived_tab="Archived",
    )
    write_sheets(workbook=workbook, postings=[_p("a")], output_config=output)

    written = workbook.companies_tab.write_rows.call_args.args[0]
    assert written[0]["assigned_to"] == "alice"
    assert written[0]["notes"] == "ping"


def test_write_sheets_archives_orphan_edits():
    workbook = MagicMock()
    workbook.companies_tab.read_rows.return_value = [
        {"company": "Gone", "assigned_to": "alice", "notes": "n"}
    ]
    workbook.postings_tab.read_rows.return_value = []

    output = OutputConfig(
        companies_tab="Companies", postings_tab="Postings", archived_tab="Archived",
    )
    write_sheets(workbook=workbook, postings=[_p("a")], output_config=output)

    workbook.archived_tab.append_rows.assert_called_once()
    appended = workbook.archived_tab.append_rows.call_args.args[0]
    assert any(r["company"] == "Gone" for r in appended)
