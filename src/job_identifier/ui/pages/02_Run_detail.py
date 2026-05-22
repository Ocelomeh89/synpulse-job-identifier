from pathlib import Path
import json
import streamlit as st

from job_identifier.config import load_runs
from job_identifier.store import Store

CONFIG_PATH = Path("config/runs.yaml")
DB_PATH = Path("data/jobs.db")

st.title("Run detail")

runs = load_runs(CONFIG_PATH)
store = Store(str(DB_PATH))
store.init_schema()

selected = st.selectbox("Run", [r.name for r in runs])
cfg = next(r for r in runs if r.name == selected)

with st.expander("Current config (from runs.yaml)"):
    st.code(str(cfg), language="python")

last_runs = list(store.db.query(
    "SELECT * FROM runs WHERE run_name = ? ORDER BY started_at DESC LIMIT 10",
    [selected],
))
if not last_runs:
    st.info("No runs yet. Trigger one from the Runs page.")
    st.stop()

st.subheader("History")
history_rows = []
for r in last_runs:
    summary = json.loads(r["summary"]) if r.get("summary") else {}
    history_rows.append({
        "Started": r["started_at"][:19],
        "Status": r["status"],
        "Filtered": summary.get("filtered", "—"),
        "New": summary.get("new", "—"),
        "Scored": summary.get("scored", "—"),
    })
st.dataframe(history_rows, use_container_width=True)

st.subheader("What's new since last run (top 10)")
latest = last_runs[0]
new_postings = list(store.db.query("""
    SELECT json_extract(p.payload, '$.company') AS company,
           json_extract(p.payload, '$.title') AS title,
           json_extract(p.payload, '$.country') AS country,
           json_extract(p.payload, '$.seniority') AS seniority,
           l.score AS score,
           json_extract(p.payload, '$.source_url') AS source_url
    FROM posting_run_link l
    JOIN postings p ON p.posting_id = l.posting_id
    WHERE l.run_id = ? AND l.is_new = 1
    ORDER BY l.score DESC
    LIMIT 10
""", [latest["run_id"]]))
if new_postings:
    st.dataframe(new_postings, use_container_width=True)
else:
    st.write("No new postings in the most recent run.")

st.subheader("Last run log")
from job_identifier.store import writable_dir_for
log_file = writable_dir_for(Path("data/logs")) / f"{latest['run_id']}.log"
if log_file.exists():
    with st.expander("Show JSON log", expanded=False):
        st.code(log_file.read_text(), language="json")
else:
    st.caption("No log file for this run.")
