from pathlib import Path
from typer.testing import CliRunner
from job_identifier.cli import app


def test_list_runs_outputs_names():
    runner = CliRunner()
    config_path = Path(__file__).parent.parent / "config" / "runs.yaml"
    result = runner.invoke(app, ["list-runs", "--config", str(config_path)])
    assert result.exit_code == 0
    assert "palantir_insurance" in result.stdout
