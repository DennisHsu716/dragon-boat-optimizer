import streamlit as st

import db

st.set_page_config(
    page_title="Dragon Boat Optimizer",
    layout="wide"
)

db.init_db()

# ---------- CSS ----------
st.markdown("""
<style>

.block-container{
    max-width:900px;
}

h1 {
text-align: center;
}
/* link */
a.card-link{
    text-decoration:none;
}

/* card */
.card{
    border:1px solid #e6eaf2;
    border-radius:22px;
    padding:50px;
    margin-bottom:30px;
    background:white;
    transition:0.2s;
    cursor:pointer;
    text-align:center;   /* ⭐ 這行就是置中 */
}

/* hover */
.card:hover{
    border:1px solid #4c8bf5;
    box-shadow:0 8px 30px rgba(0,0,0,0.08);
}

/* title */
.card-title{
    font-size:36px;
    font-weight:800;
}

/* description */
.card-desc{
    font-size:18px;
    color:#666;
    margin-top:10px;
}

</style>
""", unsafe_allow_html=True)


# ---------- Title ----------
st.title("🚣 Dragon Boat Optimizer")


# ---------- Login gate ----------
if not st.session_state.get("team_id"):
    st.caption("Log in with your team's shared account, or create a new one.")

    login_tab, register_tab = st.tabs(["Log In", "Create Team"])

    with login_tab:
        with st.form("login_form"):
            login_team_name = st.text_input("Team name", key="login_team_name")
            login_password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log In", use_container_width=True)

        if submitted:
            team_id = db.login_team(login_team_name, login_password)
            if team_id is None:
                st.error("Invalid team name or password.")
            else:
                st.session_state["team_id"] = team_id
                st.session_state["team_name"] = login_team_name.strip()
                st.rerun()

    with register_tab:
        with st.form("register_form"):
            new_team_name = st.text_input("Team name", key="new_team_name")
            new_password = st.text_input("Password", type="password", key="new_password")
            new_password_confirm = st.text_input("Confirm password", type="password", key="new_password_confirm")
            import_legacy = False
            if db.LEGACY_CSV_PATH.exists():
                import_legacy = st.checkbox(
                    f"Import existing data from {db.LEGACY_CSV_PATH} into this team",
                    value=True,
                )
            submitted = st.form_submit_button("Create Team", use_container_width=True)

        if submitted:
            if new_password != new_password_confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    team_id = db.register_team(new_team_name, new_password)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.session_state["team_id"] = team_id
                    st.session_state["team_name"] = new_team_name.strip()

                    if import_legacy:
                        n = db.import_legacy_csv(team_id, lower_is_better=True)
                        if n:
                            st.success(f"Team created. Imported {n} rows from {db.LEGACY_CSV_PATH}.")
                        else:
                            st.success("Team created.")
                    else:
                        st.success("Team created.")

                    st.rerun()

    st.stop()


# ---------- Logged in: top bar ----------
top_col1, top_col2 = st.columns([6, 1])
with top_col1:
    st.caption(f"Logged in as team: **{st.session_state.get('team_name', '')}**")
with top_col2:
    if st.button("Log Out", use_container_width=True):
        import auth
        auth.logout()
        st.rerun()


# ---------- Upload ----------
st.markdown("""
<a class="card-link" href="/Upload_Data">
<div class="card">
<div class="card-title">📂 Upload</div>
<div class="card-desc">Upload roster and score data</div>
</div>
</a>
""", unsafe_allow_html=True)


# ---------- Rank ----------
st.markdown("""
<a class="card-link" href="/Rank">
<div class="card">
<div class="card-title">🏁 Rank</div>
<div class="card-desc">View paddler rankings</div>
</div>
</a>
""", unsafe_allow_html=True)


# ---------- Lineup ----------
st.markdown("""
<a class="card-link" href="/Lineup">
<div class="card">
<div class="card-title">🚣 Lineup</div>
<div class="card-desc">Generate optimized lineup</div>
</div>
</a>
""", unsafe_allow_html=True)


#---------- Setting ----------
st.markdown("""
<a class="card-link" href="/Settings">
<div class="card">
<div class="card-title">⚙️ Settings</div>
<div class="card-desc">Configure formulas and system preferences</div>
</div>
</a>
""", unsafe_allow_html=True)
