from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

import typer

from job_identifier.config import load_runs, load_secrets
from job_identifier.runner import run as run_pipeline
from job_identifier.store import Store

app = typer.Typer(help="Job Identifier CLI")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@app.command("list-runs")
def list_runs(
    config: Path = typer.Option(Path("config/runs.yaml"), "--config", "-c"),
):
    runs = load_runs(config)
    for r in runs:
        marker = "✓" if r.enabled else "✗"
        typer.echo(f"  {marker} {r.name}  ({len(r.geos)} geos, {len(r.skill.query_terms)} queries)")


@app.command("run")
def run_cmd(
    name: str = typer.Argument(..., help="Run name from config"),
    config: Path = typer.Option(Path("config/runs.yaml"), "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    db: Path = typer.Option(Path("data/jobs.db"), "--db"),
):
    runs = load_runs(config)
    selected = next((r for r in runs if r.name == name), None)
    if selected is None:
        typer.echo(f"No run named {name!r}", err=True)
        raise typer.Exit(code=1)

    secrets = load_secrets(run_names=[name])
    store = Store(str(db))
    store.init_schema()

    result = run_pipeline(
        run_config=selected,
        secrets=secrets,
        store=store,
        now=datetime.now(),
        dry_run=dry_run,
    )
    typer.echo(f"\nRun {result.run_id}: status={result.status}")
    for k, v in result.summary.items():
        typer.echo(f"  {k}: {v}")
    if result.error:
        typer.echo(f"  error: {result.error}", err=True)
        raise typer.Exit(code=1)
