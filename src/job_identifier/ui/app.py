import os

import streamlit as st

# Bridge st.secrets → env vars so config.load_secrets() works on Streamlit Cloud.
# Local dev still uses .env via python-dotenv; this is a no-op when secrets is empty.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    pass

st.set_page_config(page_title="Job Identifier", layout="wide")
st.title("Job Identifier")
st.write("Select a page from the sidebar.")
