import streamlit as st

import auth

st.set_page_config(page_title="Settings", layout="wide")

auth.require_login()

col1, col2 = st.columns([1, 10])

with col1:
    if st.button("🏠", key="settings_home"):
        st.switch_page("app.py")

st.title("⚙️ Settings")
st.caption("Choose what you want to manage.")

st.markdown("""
<style>
.card-link{
    text-decoration:none;
}
.card{
    border:1px solid #e6eaf2;
    border-radius:22px;
    padding:40px;
    margin-bottom:24px;
    background:white;
    transition:0.2s;
    cursor:pointer;
    text-align:center;
}
.card:hover{
    border:1px solid #4c8bf5;
    box-shadow:0 8px 30px rgba(0,0,0,0.08);
}
.card-title{
    font-size:36px;
    font-weight:800;
    color:#222637;
}
.card-desc{
    font-size:18px;
    color:#666;
    margin-top:10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<a class="card-link" href="/Formula_Settings">
<div class="card">
<div class="card-title">⚙️ Formula Settings</div>
<div class="card-desc">Configure scoring formula, test type, and race distance</div>
</div>
</a>
""", unsafe_allow_html=True)

st.markdown("""
<a class="card-link" href="/Report_Issue">
<div class="card">
<div class="card-title">🐞 Report an Issue</div>
<div class="card-desc">Report bugs, feedback, or problems with rankings and lineup</div>
</div>
</a>
""", unsafe_allow_html=True)