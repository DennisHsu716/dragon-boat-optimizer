import streamlit as st

import auth
import db

st.set_page_config(page_title="Report Issue", layout="wide")

team_id = auth.require_login()

col1, col2 = st.columns([1, 10])

with col1:
    if st.button("⬅️", key="back_to_settings_issue"):
        st.switch_page("pages/4_Settings.py")

st.title("🐞 Report an Issue")
st.caption("Report bugs, unclear results, or feature requests.")

issue_type = st.selectbox(
    "Issue type",
    ["Bug", "Formula issue", "Ranking issue", "Lineup issue", "Feature request", "Other"]
)

issue_title = st.text_input("Title")
issue_desc = st.text_area("Describe the issue", height=180)

if st.button("Submit Report", use_container_width=True):
    if not issue_title.strip():
        st.error("Please enter a title.")
    elif not issue_desc.strip():
        st.error("Please describe the issue.")
    else:
        db.save_issue(team_id, issue_type, issue_title.strip(), issue_desc.strip())
        st.success("Issue submitted.")