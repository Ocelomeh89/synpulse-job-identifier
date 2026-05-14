from pathlib import Path
import json
import streamlit as st

from job_identifier.store import Store

DB_PATH = Path("data/jobs.db")

st.title("Browse postings")

store = Store(str(DB_PATH))
store.init_schema()

all_postings = list(store.db.query("""
    SELECT p.posting_id AS posting_id,
           json_extract(p.payload, '$.company') AS company,
           json_extract(p.payload, '$.title') AS title,
           json_extract(p.payload, '$.country') AS country,
           json_extract(p.payload, '$.role_type') AS role_type,
           json_extract(p.payload, '$.seniority') AS seniority,
           json_extract(p.payload, '$.posted_date') AS posted_date,
           json_extract(p.payload, '$.score') AS score,
           json_extract(p.payload, '$.source_url') AS source_url
    FROM postings p
"""))

if not all_postings:
    st.info("No postings yet. Trigger a run from the Runs page.")
    st.stop()

countries = sorted({p["country"] for p in all_postings if p.get("country")})
role_types = sorted({p["role_type"] for p in all_postings if p.get("role_type")})
seniorities = sorted({p["seniority"] for p in all_postings if p.get("seniority")})

with st.sidebar:
    st.header("Filters")
    selected_countries = st.multiselect("Country", countries, default=countries)
    selected_role_types = st.multiselect("Role type", role_types, default=role_types)
    selected_seniorities = st.multiselect("Seniority", seniorities, default=seniorities)
    min_score, max_score = st.slider("Score range", 0.0, 1.0, (0.0, 1.0), 0.05)

filtered = [
    p for p in all_postings
    if p["country"] in selected_countries
    and p["role_type"] in selected_role_types
    and p["seniority"] in selected_seniorities
    and min_score <= float(p["score"] or 0) <= max_score
]
filtered.sort(key=lambda p: float(p["score"] or 0), reverse=True)
st.dataframe(filtered, use_container_width=True)
