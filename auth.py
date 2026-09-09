from __future__ import annotations

import streamlit as st


def require_login() -> int:
    """Call at the top of every page. Redirects to the login gate if not logged in."""
    team_id = st.session_state.get("team_id")
    if not team_id:
        st.warning("Please log in first.")
        st.switch_page("app.py")
        st.stop()
    return team_id


def current_team_id() -> int:
    return st.session_state["team_id"]


def current_team_name() -> str:
    return st.session_state.get("team_name", "")


def logout() -> None:
    for key in ("team_id", "team_name"):
        st.session_state.pop(key, None)
