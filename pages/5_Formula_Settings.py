import streamlit as st

import auth
import db
from safe_eval import safe_eval, FormulaError

st.set_page_config(page_title="Settings", layout="wide")

team_id = auth.require_login()

DEFAULT_FORMULA = "((272.2 + 48.888)/(weight + 48.888))**0.1666 * time_trial"
DEFAULT_TEST_TYPE = "time"
DEFAULT_RACE_DISTANCE = 0

if "formula_settings_loaded" not in st.session_state:
    saved = db.load_team_settings(team_id)
    st.session_state["custom_test_type"] = saved["custom_test_type"] or DEFAULT_TEST_TYPE
    st.session_state["race_distance_m"] = saved["race_distance_m"] or DEFAULT_RACE_DISTANCE
    st.session_state["custom_formula"] = saved["custom_formula"] or DEFAULT_FORMULA
    st.session_state["formula_mode"] = saved["formula_mode"] or "default"
    st.session_state["formula_settings_loaded"] = True

col1, col2 = st.columns([1, 10])

with col1:
    if st.button("⬅️", key="back_to_settings_issue"):
        st.switch_page("pages/4_Settings.py")

st.title("⚙️ Settings")
st.caption("Configure the adjusted-score formula used by the system.")

formula_mode = st.radio(
    "Formula mode",
    options=["default", "custom"],
    format_func=lambda x: "Default formula" if x == "default" else "Custom formula",
    key="formula_mode"
)

if st.session_state["formula_mode"] == "default":
    st.code(DEFAULT_FORMULA)
    st.info("The system will use the default adjusted-score formula.")
else:
    st.subheader("Custom Formula Settings")

    st.radio(
        "Test input type",
        options=["time", "distance"],
        format_func=lambda x: "Time based test" if x == "time" else "Distance based test",
        key="custom_test_type"
    )

    if st.session_state["custom_test_type"] == "time":
        st.caption("Use this if your team records completion time, e.g. 500m in 2:38.1")
    else:
        st.caption("Use this if your team records distance covered in a fixed time, e.g. 2 minutes = 430m")

    st.number_input(
        "Race distance (optional, meters)",
        min_value=0,
        step=50,
        key="race_distance_m",
        help="Leave as 0 if your team does not use a race-distance conversion."
    )

    st.text_area(
        "Custom formula",
        key="custom_formula",
        height=140,
        help="""
Available variables:
- weight
- time_trial
- distance
- race_distance

Use Python-style syntax, for example:
((272.2 + 48.888)/(weight + 48.888))**0.1666 * time_trial
"""
    )

    st.caption("Example formulas")

    st.code(
        "((272.2 + 48.888)/(weight + 48.888))**0.1666 * time_trial",
        language="python"
    )

    st.code(
        "distance * (weight / 160)**0.12",
        language="python"
    )

if st.button("Save Formula", use_container_width=True):
    if st.session_state["formula_mode"] == "default":
        st.session_state["custom_formula"] = DEFAULT_FORMULA
        can_save = True
    else:
        sample_vars = {
            "weight": 150.0,
            "time_trial": 120.0,
            "distance": 430.0,
            "race_distance": float(st.session_state["race_distance_m"]),
        }
        try:
            safe_eval(st.session_state["custom_formula"], sample_vars)
            can_save = True
        except FormulaError as e:
            st.error(f"Formula is invalid: {e}")
            can_save = False

    if can_save:
        db.save_formula_settings(
            team_id,
            formula_mode=st.session_state["formula_mode"],
            custom_test_type=st.session_state["custom_test_type"],
            race_distance_m=st.session_state["race_distance_m"],
            custom_formula=st.session_state["custom_formula"],
        )
        st.success("Settings saved.")

st.divider()
st.subheader("Current Active Settings")

st.write("Formula mode:", st.session_state["formula_mode"])
st.write("Test input type:", st.session_state["custom_test_type"])
st.write("Race distance:", st.session_state["race_distance_m"])

if st.session_state["formula_mode"] == "default":
    st.code(DEFAULT_FORMULA, language="python")
else:
    st.code(st.session_state["custom_formula"], language="python")