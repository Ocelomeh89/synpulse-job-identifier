from datetime import datetime
from pathlib import Path
import json
import streamlit as st

from job_identifier.config import load_runs, load_secrets
from job_identifier.runner import run as run_pipeline
from job_identifier.store import Store

CONFIG_PATH = Path("config/runs.yaml")
DB_PATH = Path("data/jobs.db")

st.title("Runs")

runs = load_runs(CONFIG_PATH)
store = Store(str(DB_PATH))
store.init_schema()

rows = []
for r in runs:
    last = store.last_run_for_name(r.name)
    if last:
        summary = json.loads(last["summary"]) if last.get("summary") else {}
        rows.append({
            "Run": r.name,
            "Last run": last["started_at"][:19],
            "Status": last["status"],
            "New": summary.get("new", "—"),
            "Total": summary.get("scored", "—"),
        })
    else:
        rows.append({
            "Run": r.name,
            "Last run": "never",
            "Status": "—",
            "New": "—",
            "Total": "—",
        })

st.dataframe(rows, width="stretch")

st.divider()
st.subheader("Trigger a run")
choice = st.selectbox("Run to execute", [r.name for r in runs if r.enabled])
dry = st.checkbox("Dry run (no Sheet write)", value=False)
if st.button("Run now", type="primary"):
    selected = next(r for r in runs if r.name == choice)
    try:
        secrets = load_secrets(run_names=[choice])
    except RuntimeError as e:
        st.error(f"Missing secret: {e}")
        st.stop()
    with st.status(f"Running {choice}...", expanded=True) as status:
        result = run_pipeline(
            run_config=selected, secrets=secrets, store=store,
            now=datetime.now(), dry_run=dry,
        )
        for k, v in result.summary.items():
            st.write(f"**{k}**: {v}")
        if result.status == "ok":
            status.update(label=f"Done ✓ ({result.status})", state="complete")
        else:
            status.update(label=f"Failed: {result.status}", state="error")
            if result.error:
                st.error(result.error)
